"""The party's public identity, and joining or withdrawing from the register without a login."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import func, select

from backend.api.deps import AdminUser, SessionDep, Today
from backend.api.install import PartyOnlyRoute
from backend.api.routers.join import _client
from backend.models import (
    AgendaIssue,
    Constituency,
    County,
    HeroSlide,
    PartyDocument,
    PartyMember,
    PartyMemberStatus,
    PartyOrgan,
    PartyValue,
    PartyVideo,
    PostKind,
    PostLabel,
    PrimaryResult,
    RegistrationCentre,
    Seat,
    Ward,
)
from backend.schemas.content import (
    AboutItemRead,
    BranchDetail,
    BranchRead,
    DocumentRead,
    IssueRead,
    LeaderRead,
    PostRead,
    ResultRead,
    SlideRead,
    VideoRead,
)
from backend.schemas.dashboard import Dashboard
from backend.schemas.party import (
    PartyJoinCreate,
    PartyJoinDone,
    PartyPlace,
    PartySettingsRead,
    PartyStats,
    PartySubscribe,
    PartySubscribed,
    PartyWithdrawn,
)
from backend.schemas.site import EMAIL
from backend.security import hash_password
from backend.services import branches, content, dashboard, home, membership, subscribers
from backend.services import party as service
from backend.services.accounts import clean_email
from backend.services.ratelimit import RateLimit
from backend.services.sms import normalise_phone

router = APIRouter(prefix="/party", tags=["party"])
# Mounted in every installation; party_router only in a party installation.
party_router = APIRouter(prefix="/party", tags=["party"], route_class=PartyOnlyRoute)

# Applications one device may send in an hour, and withdrawal attempts.
JOINS = RateLimit(limit=20, window=3600)
WITHDRAWALS = RateLimit(limit=20, window=3600)
VOLUNTEER_WITHDRAWALS = RateLimit(limit=20, window=3600)
SUBSCRIBES = RateLimit(limit=20, window=3600)
UNSUBSCRIBES = RateLimit(limit=20, window=3600)
UNSUBSCRIBE_PATH = "/unsubscribe/"
WITHDRAW_PATH = "/party/withdraw/"
VOLUNTEER_WITHDRAW_PATH = "/party/volunteer/withdraw/"
# The same answer for every code, so a code cannot be tested for whether it was real.
WITHDRAWN = (
    "Received. If this link came with the application that put your number on the register, "
    "that application or membership will be withdrawn within a few minutes, and the party keeps "
    "the record with the status withdrawn. Otherwise this link changes nothing: ask the party "
    "to withdraw you."
)
VOLUNTEER_WITHDRAWN = (
    "Received. If this link came with your volunteer sign-up, the party will stop contacting you "
    "about volunteering within a few minutes. Your membership is unchanged."
)

SUBSCRIBED = "Thank you. You will get our news there; the link below unsubscribes you."
UNSUBSCRIBED = (
    "Received. If this link came with a news sign-up, that contact gets no more news from us."
)


def _well_formed(code: str) -> bool:
    """Codes are url-safe and at most 32 characters; anything else matches nothing."""
    return len(code) <= 32 and code.replace("-", "").replace("_", "").isalnum() and code.isascii()


@party_router.get("/", response_model=PartySettingsRead)
async def get_party(session: SessionDep) -> PartySettingsRead:
    return await service.read_settings(session)


@party_router.get("/leaders/", response_model=list[LeaderRead])
async def leaders(session: SessionDep):
    """The published leaders, in the order the party set."""
    return await content.published_leaders(session)


@party_router.get("/branches/", response_model=list[BranchRead])
async def party_branches(session: SessionDep):
    """The published county branches, by county name."""
    return await branches.published(session)


@party_router.get("/branches/{county_id}/", response_model=BranchDetail)
async def party_branch(county_id: uuid.UUID, session: SessionDep):
    """A published branch, with its county's constituencies and wards."""
    return await branches.published_detail(session, county_id)


@router.get("/posts/", response_model=list[PostRead])
async def posts(
    session: SessionDep,
    today: Today,
    kind: PostKind,
    offset: int = Query(default=0, ge=0),
    label: PostLabel | None = None,
    county: uuid.UUID | None = None,
):
    """Published news, newest first and paged, optionally one label; or published events from
    today on, soonest first, optionally in one county."""
    if kind is PostKind.EVENT:
        return await content.upcoming_events(session, today, county)
    return await content.published_news(session, offset, label)


@router.get("/posts/{post_id}/", response_model=PostRead)
async def post(post_id: uuid.UUID, session: SessionDep):
    return await content.published_post(session, post_id)


@party_router.get("/dashboard/", response_model=Dashboard)
async def party_dashboard(
    session: SessionDep,
    _: AdminUser,
    today: Today,
    county: uuid.UUID | None = None,
    constituency: uuid.UUID | None = None,
    ward: uuid.UUID | None = None,
    seat: Seat | None = None,
    aspirant: uuid.UUID | None = None,
    start: Annotated[date | None, Query(alias="from")] = None,
    end: Annotated[date | None, Query(alias="to")] = None,
) -> Dashboard:
    """Party-wide counts; without dates, events cover the next 30 days."""
    if start and end and start > end:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The start date is after the end date.")
    filters = dashboard.Filters(county, constituency, ward, seat, aspirant, start, end)
    return await dashboard.dashboard(session, filters, today)


@router.get("/places/", response_model=list[PartyPlace])
async def places(
    session: SessionDep,
    county: uuid.UUID | None = None,
    constituency: uuid.UUID | None = None,
    ward: uuid.UUID | None = None,
) -> list[PartyPlace]:
    """Counties; a county's constituencies; a constituency's wards; or a ward's polling
    stations, by name."""
    if ward is not None:
        statement = (
            select(RegistrationCentre)
            .where(RegistrationCentre.ward_id == ward)
            .order_by(RegistrationCentre.name)
        )
    elif constituency is not None:
        statement = select(Ward).where(Ward.constituency_id == constituency).order_by(Ward.name)
    elif county is not None:
        statement = (
            select(Constituency).where(Constituency.county_id == county).order_by(Constituency.name)
        )
    else:
        statement = select(County).order_by(County.name)
    return list(await session.scalars(statement))


@party_router.post("/join/", response_model=PartyJoinDone, status_code=status.HTTP_201_CREATED)
async def join(payload: PartyJoinCreate, request: Request, session: SessionDep) -> PartyJoinDone:
    """Queue an application to join the party; the register changes out of band.

    Every valid application is the same single insert, so neither the answer nor its timing
    shows whether the phone is already registered.
    """
    if not JOINS.allow(_client(request)):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many applications from this device; try later."
        )
    phone = normalise_phone(payload.phone)
    if phone is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Enter a Kenyan mobile number, like 0712 345678."
        )
    if await session.get(Ward, payload.ward) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No such ward.")
    centre = await session.get(RegistrationCentre, payload.registration_centre)
    if centre is None or centre.ward_id != payload.ward:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Choose a polling station in the ward you chose."
        )
    code, volunteer_code = membership.request_join(
        session,
        first_name=payload.first_name,
        surname=payload.surname,
        phone=phone,
        email=payload.email,
        password_hash=hash_password(payload.password),
        ward_id=payload.ward,
        registration_centre_id=payload.registration_centre,
        volunteer=payload.volunteer.model_dump() if payload.volunteer else None,
        recruitment=payload.recruitment,
    )
    await session.commit()
    return PartyJoinDone(
        withdraw_url=f"{WITHDRAW_PATH}{code}",
        volunteer_withdraw_url=(
            f"{VOLUNTEER_WITHDRAW_PATH}{volunteer_code}" if volunteer_code else None
        ),
    )


@party_router.post("/withdraw/{code}/", response_model=PartyWithdrawn)
async def withdraw(code: str, request: Request, session: SessionDep) -> PartyWithdrawn:
    """Queue a withdrawal by code; the answer is the same for any code."""
    if not WITHDRAWALS.allow(_client(request)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many tries; try later.")
    if _well_formed(code):
        membership.request_withdraw(session, code)
        await session.commit()
    return PartyWithdrawn(message=WITHDRAWN)


@party_router.post("/volunteer/withdraw/{code}/", response_model=PartyWithdrawn)
async def withdraw_volunteer(code: str, request: Request, session: SessionDep) -> PartyWithdrawn:
    """Queue a volunteer withdrawal by code; the answer is the same for any code."""
    if not VOLUNTEER_WITHDRAWALS.allow(_client(request)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many tries; try later.")
    if _well_formed(code):
        membership.request_volunteer_withdraw(session, code)
        await session.commit()
    return PartyWithdrawn(message=VOLUNTEER_WITHDRAWN)


@router.post("/subscribe/", response_model=PartySubscribed, status_code=status.HTTP_201_CREATED)
async def subscribe(
    payload: PartySubscribe, request: Request, session: SessionDep
) -> PartySubscribed:
    """Sign a phone or email up for party news; a known contact gets the same answer."""
    if not SUBSCRIBES.allow(_client(request)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many sign-ups; try later.")
    if "@" in payload.contact:
        contact = clean_email(payload.contact)
        if not EMAIL.match(contact):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Use an email address like name@example.com."
            )
        channel = "email"
    else:
        contact = normalise_phone(payload.contact)
        if contact is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Enter a Kenyan mobile number, like 0712 345678."
            )
        channel = "sms"
    code = await subscribers.subscribe(session, contact, channel)
    await session.commit()
    return PartySubscribed(message=SUBSCRIBED, unsubscribe_url=f"{UNSUBSCRIBE_PATH}{code}")


@router.post("/unsubscribe/{code}/", response_model=PartyWithdrawn)
async def unsubscribe(code: str, request: Request, session: SessionDep) -> PartyWithdrawn:
    """Remove a news sign-up by its code; the answer is the same for any code."""
    if not UNSUBSCRIBES.allow(_client(request)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many tries; try later.")
    if _well_formed(code):
        await subscribers.unsubscribe(session, code)
        await session.commit()
    return PartyWithdrawn(message=UNSUBSCRIBED)


@router.get("/slides/", response_model=list[SlideRead])
async def slides(session: SessionDep):
    """The published carousel slides, in order."""
    return await home.published(session, HeroSlide)


@router.get("/issues/", response_model=list[IssueRead])
async def issues(session: SessionDep):
    """The published agenda issues, in order."""
    return await home.published(session, AgendaIssue)


@router.get("/issues/{issue_id}/", response_model=IssueRead)
async def issue(issue_id: uuid.UUID, session: SessionDep):
    return await home.published_issue(session, issue_id)


@router.get("/documents/", response_model=list[DocumentRead])
async def documents(session: SessionDep):
    """The published party documents, in order."""
    return await home.published(session, PartyDocument)


@party_router.get("/values/", response_model=list[AboutItemRead])
async def values(session: SessionDep):
    """The party's published values, in order."""
    return await home.published(session, PartyValue)


@party_router.get("/organs/", response_model=list[AboutItemRead])
async def organs(session: SessionDep):
    """The party's published organs, in order."""
    return await home.published(session, PartyOrgan)


@router.get("/videos/", response_model=list[VideoRead])
async def videos(session: SessionDep):
    """The published videos for the homepage's Watch row, in order."""
    return await home.published(session, PartyVideo)


@party_router.get("/results/", response_model=list[ResultRead])
async def results(session: SessionDep):
    """The published primary results, by seat, area and votes, most votes first."""
    return await home.published(session, PrimaryResult)


@party_router.get("/stats/", response_model=PartyStats)
async def stats(session: SessionDep) -> PartyStats:
    """How many approved members the party has and how many county branches are published."""
    return PartyStats(
        members=await session.scalar(
            select(func.count())
            .select_from(PartyMember)
            .where(PartyMember.status == PartyMemberStatus.APPROVED)
        ),
        branches=len(await branches.published(session)),
    )
