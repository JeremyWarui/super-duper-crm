"""Nominations for the nominations officer: candidates, list, detail, nominate, status moves."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import AfterValidator

from backend.api.deps import NominationsOfficer, SessionDep
from backend.api.install import PartyOnlyRoute
from backend.models import Aspirant, AspirantStatus, Seat
from backend.schemas.admin import AdminUserCreated
from backend.schemas.aspirants import (
    AspirantArea,
    AspirantCreate,
    AspirantMove,
    AspirantPage,
    AspirantRead,
    CandidateRead,
    DocumentRead,
    WorkspaceCreate,
    WorkspaceCreated,
)
from backend.schemas.common import plain_text
from backend.services import aspirants
from backend.services.aspirants import AspirantFilters
from backend.services.campaigns import AREA_FIELD

router = APIRouter(prefix="/party/aspirants", tags=["party"], route_class=PartyOnlyRoute)


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
        window_title=row.window.title if row.window else None,
        fee_kes=row.fee_kes,
        fee_paid_at=row.fee_paid_at,
        fee_reference=row.fee_reference,
        declared_at=row.declared_at,
        documents=[DocumentRead(id=d.id, label=d.label) for d in row.documents],
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
    q: Annotated[str, Query(max_length=100), AfterValidator(plain_text)] = "",
) -> list:
    """Approved members without a live nomination, by name or exact full phone; at most 20."""
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
    total, rows = await aspirants.aspirants(session, filters, limit, offset)
    return AspirantPage(total=total, items=[_read(row) for row in rows])


@router.get("/{aspirant_id}/", response_model=AspirantRead)
async def get_aspirant(
    aspirant_id: uuid.UUID, user: NominationsOfficer, session: SessionDep
) -> AspirantRead:
    return _read(await aspirants.get_aspirant(session, aspirant_id))


@router.post("/", response_model=AspirantRead, status_code=status.HTTP_201_CREATED)
async def nominate(
    payload: AspirantCreate, user: NominationsOfficer, session: SessionDep
) -> AspirantRead:
    """A draft nomination for an approved member on a seat and its area."""
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
    aspirant = await aspirants.get_aspirant(session, aspirant_id)
    await aspirants.move(session, aspirant, payload.status, actor=user, reason=payload.reason)
    await session.commit()
    return _read(await aspirants.get_aspirant(session, aspirant_id))


@router.post(
    "/{aspirant_id}/workspace/",
    response_model=WorkspaceCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace(
    aspirant_id: uuid.UUID, payload: WorkspaceCreate, user: NominationsOfficer, session: SessionDep
) -> WorkspaceCreated:
    """An approved aspirant's campaign on their seat and area; its logins are sent invite links."""
    aspirant = await aspirants.get_aspirant(session, aspirant_id)
    _, summary, logins = await aspirants.create_workspace(
        session,
        aspirant,
        actor=user,
        candidate=payload.candidate.model_dump(),
        manager=payload.manager.model_dump() if payload.manager else None,
        title=payload.title,
        election_date=payload.election_date,
    )
    return WorkspaceCreated(
        aspirant=_read(await aspirants.get_aspirant(session, aspirant_id)),
        setup=summary,
        logins=[
            AdminUserCreated(
                id=login.id,
                username=login.username,
                full_name=login.full_name,
                role=login.role,
                invite=invite,
            )
            for login, invite in logins
        ],
    )
