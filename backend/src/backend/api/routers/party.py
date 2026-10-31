"""The party's public identity, and joining or withdrawing from the register without a login."""

import uuid

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from backend.api.deps import SessionDep
from backend.api.routers.join import _client
from backend.models import (
    Constituency,
    County,
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
from backend.services.ratelimit import RateLimit
from backend.services.sms import normalise_phone

router = APIRouter(prefix="/party", tags=["party"])

# Applications one device may send in an hour, and withdrawal attempts.
JOINS = RateLimit(limit=20, window=3600)
WITHDRAWALS = RateLimit(limit=20, window=3600)
WITHDRAW_PATH = "/party/withdraw/"
# The same answer for every code, so a code cannot be tested for whether it was real.
WITHDRAWN = (
    "Received. If this link came with the application that put your number on the register, "
    "that application or membership will be withdrawn within a few minutes, and the party keeps "
    "the record with the status withdrawn. Otherwise this link changes nothing: ask the party "
    "to withdraw you."
)


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
    code = membership.request_join(
        session,
        full_name=payload.full_name,
        phone=phone,
        email=payload.email or None,
        ward_id=payload.ward,
    )
    await session.commit()
    return PartyJoinDone(withdraw_url=f"{WITHDRAW_PATH}{code}")


@router.post("/withdraw/{code}/", response_model=PartyWithdrawn)
async def withdraw(code: str, request: Request, session: SessionDep) -> PartyWithdrawn:
    """Queue a withdrawal by code; the answer is the same for any code."""
    if not WITHDRAWALS.allow(_client(request)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many tries; try later.")
    # Codes are url-safe and at most 32 characters; anything else matches nothing.
    if len(code) <= 32 and code.replace("-", "").replace("_", "").isalnum() and code.isascii():
        membership.request_withdraw(session, code)
        await session.commit()
    return PartyWithdrawn(message=WITHDRAWN)
