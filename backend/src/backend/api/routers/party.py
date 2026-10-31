"""The party's public identity, and joining or withdrawing from the register without a login."""

import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.api.deps import SessionDep
from backend.api.routers.join import _client
from backend.models import PartyConsentChannel, PartyMember, PartyMemberStatus, Ward
from backend.schemas.party import PartyJoinCreate, PartyJoinDone, PartySettingsRead, PartyWithdrawn
from backend.services import membership
from backend.services import party as service
from backend.services.consent import PARTY_WORDING
from backend.services.ratelimit import RateLimit
from backend.services.sms import normalise_phone

router = APIRouter(prefix="/party", tags=["party"])

# Applications one device may send in an hour, and withdrawal attempts.
JOINS = RateLimit(limit=20, window=3600)
WITHDRAWALS = RateLimit(limit=20, window=3600)
WITHDRAW_PATH = "/party/withdraw/"
# The same answer for every code, so a code cannot be tested for whether it was real.
WITHDRAWN = "Done. If you were on the party register, you are off it now."
S = PartyMemberStatus


@router.get("/", response_model=PartySettingsRead)
async def get_party(session: SessionDep) -> PartySettingsRead:
    return await service.read_settings(session)


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
    elif member.status in (S.REJECTED, S.WITHDRAWN):
        membership.check_move(member.status, S.PENDING)
        member.status = S.PENDING
        member.full_name = payload.full_name
        member.email = payload.email or None
        member.ward_id = payload.ward
        member.consent_channel = PartyConsentChannel.WEB_FORM
        member.consent_wording = wording
        member.consent_at = datetime.now(UTC)
        member.status_reason = None
        member.decided_at = None
        member.decided_by_id = None
        member.withdraw_code = code
    else:
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
        membership.withdraw(member)
        await session.commit()
    return PartyWithdrawn(message=WITHDRAWN)
