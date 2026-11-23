"""The public website: posts, homepage content, places, and news sign-ups."""

import uuid

from fastapi import APIRouter, Query, Request, status

from backend.api.deps import SessionDep, Today
from backend.api.limits import check
from backend.models import (
    AgendaIssue,
    Constituency,
    County,
    Document,
    HeroSlide,
    PostKind,
    PostLabel,
    RegistrationCentre,
    Video,
    Ward,
)
from backend.schemas.common import Named
from backend.schemas.content import DocumentRead, IssueRead, PostRead, SlideRead, VideoRead
from backend.schemas.site import EMAIL, EMAIL_EXAMPLE
from backend.schemas.website import Received, Subscribe, Subscribed
from backend.services import content, geography, home, subscribers
from backend.services.accounts import clean_email
from backend.services.errors import Refused
from backend.services.ratelimit import RateLimit
from backend.services.sms import require_phone

router = APIRouter(prefix="/website", tags=["website"])

SUBSCRIBES = RateLimit(limit=20, window=3600)
UNSUBSCRIBES = RateLimit(limit=20, window=3600)
UNSUBSCRIBE_PATH = "/unsubscribe/"

SUBSCRIBED = "Thank you. You will get our news there; the link below unsubscribes you."
UNSUBSCRIBED = (
    "Received. If this link came with a news sign-up, that contact gets no more news from us."
)


def _well_formed(code: str) -> bool:
    """Codes are url-safe and at most 32 characters; anything else matches nothing."""
    return len(code) <= 32 and code.replace("-", "").replace("_", "").isalnum() and code.isascii()


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


@router.get("/places/", response_model=list[Named])
async def places(
    session: SessionDep,
    county: uuid.UUID | None = None,
    constituency: uuid.UUID | None = None,
    ward: uuid.UUID | None = None,
) -> list[Named]:
    """Counties; a county's constituencies; a constituency's wards; or a ward's polling
    stations, by name."""
    if ward is not None:
        return await geography.places(session, RegistrationCentre, ward)
    if constituency is not None:
        return await geography.places(session, Ward, constituency)
    if county is not None:
        return await geography.places(session, Constituency, county)
    return await geography.places(session, County)


@router.post("/subscribe/", response_model=Subscribed, status_code=status.HTTP_201_CREATED)
async def subscribe(payload: Subscribe, request: Request, session: SessionDep) -> Subscribed:
    """Sign a phone or email up for news; a known contact gets the same answer."""
    check(SUBSCRIBES, request, "Too many sign-ups; try later.")
    if "@" in payload.contact:
        contact = clean_email(payload.contact)
        if not EMAIL.match(contact):
            raise Refused(EMAIL_EXAMPLE)
        channel = "email"
    else:
        contact = require_phone(payload.contact)
        channel = "sms"
    code = await subscribers.subscribe(session, contact, channel)
    await session.commit()
    return Subscribed(message=SUBSCRIBED, unsubscribe_url=f"{UNSUBSCRIBE_PATH}{code}")


@router.post("/unsubscribe/{code}/", response_model=Received)
async def unsubscribe(code: str, request: Request, session: SessionDep) -> Received:
    """Remove a news sign-up by its code; the answer is the same for any code."""
    check(UNSUBSCRIBES, request)
    if _well_formed(code):
        await subscribers.unsubscribe(session, code)
        await session.commit()
    return Received(message=UNSUBSCRIBED)


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
    """The published documents, in order."""
    return await home.published(session, Document)


@router.get("/videos/", response_model=list[VideoRead])
async def videos(session: SessionDep):
    """The published videos for the homepage's Watch row, in order."""
    return await home.published(session, Video)
