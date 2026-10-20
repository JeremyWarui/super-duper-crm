"""The public sign-up behind an event's QR code: no login, one supporter per phone."""

import ipaddress
import os

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.api.deps import SessionDep
from backend.models import Campaign, Event, EventStatus, Supporter, SupportLevel
from backend.schemas.join import JoinCreate, JoinDone, JoinRead
from backend.services.ratelimit import RateLimit
from backend.services.sms import normalise_phone

router = APIRouter(prefix="/join", tags=["join"])

# Sign-ups one device may send in an hour.
SIGNUPS = RateLimit(limit=20, window=3600)
THANKS = "Thank you, you're signed up."


async def _event(session: SessionDep, code: str) -> Event:
    event = await session.scalar(
        select(Event)
        .where(Event.signup_code == code)
        .options(
            selectinload(Event.ward),
            selectinload(Event.campaign).selectinload(Campaign.candidate),
        )
    )
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This sign-up link is not valid.")
    return event


def _client(request: Request) -> str:
    """Who is signing up, for the rate limit: the address Fly saw, or the connection's own.

    An IPv6 client is keyed by its /64, which one device can roam within.
    """
    raw = request.headers.get("fly-client-ip") if os.environ.get("FLY_APP_NAME") else None
    raw = raw or (request.client.host if request.client else "")
    try:
        address = ipaddress.ip_address(raw)
    except ValueError:
        return raw
    if address.version == 6:
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(address)


def _open(event: Event) -> bool:
    return event.signups_open and event.status is not EventStatus.CANCELLED


@router.get("/{code}/", response_model=JoinRead)
async def read_signup(code: str, session: SessionDep) -> JoinRead:
    event = await _event(session, code)
    candidate = event.campaign.candidate
    return JoinRead(
        campaign_title=event.campaign.title,
        candidate_name=(candidate.full_name or candidate.username) if candidate else "",
        event_title=event.title,
        ward_name=event.ward.name,
        open=_open(event),
    )


@router.post("/{code}/", response_model=JoinDone, status_code=status.HTTP_201_CREATED)
async def sign_up(
    code: str, payload: JoinCreate, request: Request, session: SessionDep
) -> JoinDone:
    """Sign a person up from the event; someone already on the register is updated, not added."""
    if not SIGNUPS.allow(_client(request)):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many sign-ups from this device; try later."
        )
    event = await _event(session, code)
    if not _open(event):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Sign-ups for this event are closed.")
    phone = normalise_phone(payload.phone)
    if phone is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Enter a Kenyan mobile number, like 0712 345678."
        )
    known = await session.scalar(
        select(Supporter.id).where(
            Supporter.campaign_id == event.campaign_id, Supporter.phone == phone
        )
    )
    # Someone already on the register is left as they are, and told the same thing.
    if known is None:
        session.add(
            Supporter(
                campaign_id=event.campaign_id,
                ward_id=event.ward_id,
                event_id=event.id,
                mobilizer_id=event.mobilizer_id,
                full_name=payload.full_name,
                phone=phone,
                support_level=SupportLevel.SUPPORTER,
                consent_given=True,
            )
        )
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()  # the same phone signed up a moment ago
    return JoinDone(message=THANKS)
