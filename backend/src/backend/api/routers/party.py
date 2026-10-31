"""The party's public identity, and joining or withdrawing from the register without a login."""

import secrets
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from backend.api.deps import SessionDep
from backend.api.routers.join import _client
from backend.models import (
    Constituency,
    County,
    PartyConsentChannel,
    PartyMember,
    PartyMemberStatus,
    Ward,
)
from backend.schemas.party import (
    PartyJoinCreate,
    PartyJoinDone,
    PartyPlace,
    PartySettingsRead,
    PartyWithdrawn,
)
from backend.services import membership
from backend.services import party as service
from backend.services.consent import PARTY_WORDING
from backend.services.errors import Refused
from backend.services.ratelimit import RateLimit
from backend.services.sms import normalise_phone

router = APIRouter(prefix="/party", tags=["party"])

# Applications one device may send in an hour, and withdrawal attempts.
JOINS = RateLimit(limit=20, window=3600)
WITHDRAWALS = RateLimit(limit=20, window=3600)
WITHDRAW_PATH = "/party/withdraw/"
# The same answer for every code, so a code cannot be tested for whether it was real.
WITHDRAWN = (
    "Done. If this link came with your application, that application or membership is now "
    "withdrawn; the party keeps your details with that status. If your number was already on "
    "the register when you applied, this link changes nothing: ask the party to withdraw you."
)
S = PartyMemberStatus


@router.get("/", response_model=PartySettingsRead)
async def get_party(session: SessionDep) -> PartySettingsRead:
    return await service.read_settings(session)


@router.get("/places/", response_model=list[PartyPlace])
async def places(
    session: SessionDep, county: uuid.UUID | None = None, constituency: uuid.UUID | None = None
) -> list[PartyPlace]:
    """Counties; a county's constituencies; or a constituency's wards, by name."""
    if constituency is not None:
        statement = select(Ward).where(Ward.constituency_id == constituency).order_by(Ward.name)
    elif county is not None:
        statement = (
            select(Constituency).where(Constituency.county_id == county).order_by(Constituency.name)
        )
    else:
        statement = select(County).order_by(County.name)
    return list(await session.scalars(statement))


def _done(code: str) -> PartyJoinDone:
    return PartyJoinDone(withdraw_url=f"{WITHDRAW_PATH}{code}")


@router.post("/join/", response_model=PartyJoinDone, status_code=status.HTTP_201_CREATED)
async def join(payload: PartyJoinCreate, request: Request, session: SessionDep) -> PartyJoinDone:
    """Apply to join the party; a phone already on the register is left as it is.

    The answer has the same shape for a new and a known phone, with a working withdrawal link
    only when a row was written, so it never shows whether the phone is registered.
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
    code = membership.new_withdraw_code()
    wording = PARTY_WORDING[PartyConsentChannel.WEB_FORM]
    member = await session.scalar(select(PartyMember).where(PartyMember.phone == phone))
    written = False
    if member is None:
        session.add(
            PartyMember(
                full_name=payload.full_name,
                phone=phone,
                email=payload.email or None,
                ward_id=payload.ward,
                status=S.PENDING,
                consent_channel=PartyConsentChannel.WEB_FORM,
                consent_wording=wording,
                consent_at=datetime.now(UTC),
                withdraw_code=code,
            )
        )
        written = True
    elif member.status in (S.REJECTED, S.WITHDRAWN):
        written = await membership.reapply(
            session,
            member,
            full_name=payload.full_name,
            email=payload.email or None,
            ward_id=payload.ward,
            consent_channel=PartyConsentChannel.WEB_FORM,
            consent_wording=wording,
            consent_at=datetime.now(UTC),
            withdraw_code=code,
        )
    if not written:
        # The same write and commit as a new application, so the timing does not tell them apart.
        await session.execute(
            update(PartyMember).where(PartyMember.id == member.id).values(phone=member.phone)
        )
        await session.commit()
        return _done(secrets.token_urlsafe(18))
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()  # the same phone applied a moment ago
    return _done(code)


@router.post("/withdraw/{code}/", response_model=PartyWithdrawn)
async def withdraw(code: str, request: Request, session: SessionDep) -> PartyWithdrawn:
    """Withdraw from the register; the answer is the same for any code."""
    if not WITHDRAWALS.allow(_client(request)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many tries; try later.")
    member = await session.scalar(select(PartyMember).where(PartyMember.withdraw_code == code))
    if member is not None and member.status in (S.PENDING, S.APPROVED, S.SUSPENDED):
        try:
            await membership.withdraw(session, member)
        except Refused:
            await (
                session.rollback()
            )  # an officer moved them a moment ago; the answer stays the same
        else:
            await session.commit()
    return PartyWithdrawn(message=WITHDRAWN)
