"""Nominations for the nominations officer: candidates, list, detail, nominate, status moves."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from backend.api.deps import NominationsOfficer, SessionDep
from backend.models import Aspirant, AspirantStatus, Seat
from backend.schemas.aspirants import (
    AspirantArea,
    AspirantCreate,
    AspirantMove,
    AspirantPage,
    AspirantRead,
    CandidateRead,
)
from backend.services import aspirants, membership
from backend.services.aspirants import AspirantFilters
from backend.services.campaigns import AREA_FIELD

router = APIRouter(prefix="/party/aspirants", tags=["party"])


def _read(row: Aspirant) -> AspirantRead:
    level = AREA_FIELD[row.seat.office_level]
    place = getattr(row, level)
    return AspirantRead(
        id=row.id,
        member=CandidateRead.model_validate(row.member),
        seat=row.seat,
        area=AspirantArea(level=level, id=place.id, name=place.name),
        status=row.status,
        status_reason=row.status_reason,
        decided_at=row.decided_at,
        campaign_id=row.campaign_id,
        created_at=row.created_at,
    )


def _filters(
    status: AspirantStatus | None = None,
    seat: Seat | None = None,
    county: uuid.UUID | None = None,
    constituency: uuid.UUID | None = None,
    ward: uuid.UUID | None = None,
) -> AspirantFilters:
    return AspirantFilters(
        status=status, seat=seat, county=county, constituency=constituency, ward=ward
    )


@router.get("/candidates/", response_model=list[CandidateRead])
async def list_candidates(
    user: NominationsOfficer,
    session: SessionDep,
    q: Annotated[str, Query(max_length=100)] = "",
) -> list:
    """Approved members without a live nomination, by name or exact full phone; at most 20."""
    await membership.process_requests(session)
    return await aspirants.candidates(session, q)


@router.get("/", response_model=AspirantPage)
async def list_aspirants(
    user: NominationsOfficer,
    session: SessionDep,
    filters: Annotated[AspirantFilters, Depends(_filters)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> AspirantPage:
    """A page of nominations, newest first."""
    await membership.process_requests(session)
    total, rows = await aspirants.aspirants(session, filters, limit, offset)
    return AspirantPage(total=total, items=[_read(row) for row in rows])


@router.get("/{aspirant_id}/", response_model=AspirantRead)
async def get_aspirant(
    aspirant_id: uuid.UUID, user: NominationsOfficer, session: SessionDep
) -> AspirantRead:
    await membership.process_requests(session)
    return _read(await aspirants.get_aspirant(session, aspirant_id))


@router.post("/", response_model=AspirantRead, status_code=status.HTTP_201_CREATED)
async def nominate(
    payload: AspirantCreate, user: NominationsOfficer, session: SessionDep
) -> AspirantRead:
    """A draft nomination for an approved member on a seat and its area."""
    await membership.process_requests(session)
    created = await aspirants.nominate(
        session,
        member_id=payload.member,
        seat=payload.seat,
        county=payload.county,
        constituency=payload.constituency,
        ward=payload.ward,
        actor=user,
    )
    await session.commit()
    return _read(await aspirants.get_aspirant(session, created.id))


@router.post("/{aspirant_id}/status/", response_model=AspirantRead)
async def move_aspirant(
    aspirant_id: uuid.UUID, payload: AspirantMove, user: NominationsOfficer, session: SessionDep
) -> AspirantRead:
    """Move a nomination along the table; rejecting and suspending need a reason."""
    await membership.process_requests(session)
    aspirant = await aspirants.get_aspirant(session, aspirant_id)
    await aspirants.move(session, aspirant, payload.status, actor=user, reason=payload.reason)
    await session.commit()
    return _read(await aspirants.get_aspirant(session, aspirant_id))
