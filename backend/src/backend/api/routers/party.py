"""The party's public identity, and joining or withdrawing from the register without a login."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import select

from backend.api.deps import AdminUser, SessionDep, Today
from backend.api.routers.join import _client
from backend.config import get_settings
from backend.models import (
    Constituency,
    County,
    PostKind,
    RegistrationCentre,
    Seat,
    Ward,
)
from backend.schemas.content import BranchDetail, BranchRead, LeaderRead, PostRead
from backend.schemas.dashboard import Dashboard
from backend.schemas.party import (
    EMAIL,
    PartyContribute,
    PartyContributed,
    PartyJoinCreate,
    PartyJoinDone,
    PartyPlace,
    PartySettingsRead,
    PartySubscribe,
    PartySubscribed,
    PartyWithdrawn,
)
from backend.security import hash_password
from backend.services import branches, content, dashboard, membership, subscribers
from backend.services import party as service
from backend.services.accounts import clean_email
from backend.services.ratelimit import RateLimit
from backend.services.sms import normalise_phone

router = APIRouter(prefix="/party", tags=["party"])

# Applications one device may send in an hour, and withdrawal attempts.
JOINS = RateLimit(limit=20, window=3600)
WITHDRAWALS = RateLimit(limit=20, window=3600)
VOLUNTEER_WITHDRAWALS = RateLimit(limit=20, window=3600)
SUBSCRIBES = RateLimit(limit=20, window=3600)
UNSUBSCRIBES = RateLimit(limit=20, window=3600)
CONTRIBUTIONS = RateLimit(limit=20, window=3600)
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

SUBSCRIBED = "Thank you. You will get party news there; the link below unsubscribes you."
UNSUBSCRIBED = (
    "Received. If this link came with a news sign-up, that contact gets no more party news."
)
CONTRIBUTED_DEMO = (
    "This is a demonstration site: no money moved and nothing was charged or stored. "
    "A party using this platform takes contributions through its payment provider."
)


def _well_formed(code: str) -> bool:
    """Codes are url-safe and at most 32 characters; anything else matches nothing."""
    return len(code) <= 32 and code.replace("-", "").replace("_", "").isalnum() and code.isascii()


@router.get("/", response_model=PartySettingsRead)
async def get_party(session: SessionDep) -> PartySettingsRead:
    return await service.read_settings(session)


@router.get("/leaders/", response_model=list[LeaderRead])
async def leaders(session: SessionDep):
    """The published leaders, in the order the party set."""
    return await content.published_leaders(session)


@router.get("/branches/", response_model=list[BranchRead])
async def party_branches(session: SessionDep):
    """The published county branches, by county name."""
    return await branches.published(session)


@router.get("/branches/{county_id}/", response_model=BranchDetail)
async def party_branch(county_id: uuid.UUID, session: SessionDep):
    """A published branch, with its county's constituencies and wards."""
    return await branches.published_detail(session, county_id)


@router.get("/posts/", response_model=list[PostRead])
async def posts(
    session: SessionDep, today: Today, kind: PostKind, offset: int = Query(default=0, ge=0)
):
    """Published news, newest first and paged; or published events from today on, soonest first."""
    if kind is PostKind.EVENT:
        return await content.upcoming_events(session, today)
    return await content.published_news(session, offset)


@router.get("/posts/{post_id}/", response_model=PostRead)
async def post(post_id: uuid.UUID, session: SessionDep):
    return await content.published_post(session, post_id)


@router.get("/dashboard/", response_model=Dashboard)
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
    """Party-wide counts; without dates, events cover the next 30 days and revenue this year."""
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


@router.post("/join/", response_model=PartyJoinDone, status_code=status.HTTP_201_CREATED)
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
    )
    await session.commit()
    return PartyJoinDone(
        withdraw_url=f"{WITHDRAW_PATH}{code}",
        volunteer_withdraw_url=(
            f"{VOLUNTEER_WITHDRAW_PATH}{volunteer_code}" if volunteer_code else None
        ),
    )


@router.post("/withdraw/{code}/", response_model=PartyWithdrawn)
async def withdraw(code: str, request: Request, session: SessionDep) -> PartyWithdrawn:
    """Queue a withdrawal by code; the answer is the same for any code."""
    if not WITHDRAWALS.allow(_client(request)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many tries; try later.")
    if _well_formed(code):
        membership.request_withdraw(session, code)
        await session.commit()
    return PartyWithdrawn(message=WITHDRAWN)


@router.post("/volunteer/withdraw/{code}/", response_model=PartyWithdrawn)
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


@router.post("/contribute/", response_model=PartyContributed)
async def contribute(payload: PartyContribute, request: Request) -> PartyContributed:
    """Take a contribution. In demo mode nothing is charged or stored."""
    if not CONTRIBUTIONS.allow(_client(request)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many tries; try later.")
    if normalise_phone(payload.phone) is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Enter a Kenyan mobile number, like 0712 345678."
        )
    return PartyContributed(
        demo=get_settings().payments_provider == "demo", message=CONTRIBUTED_DEMO
    )
