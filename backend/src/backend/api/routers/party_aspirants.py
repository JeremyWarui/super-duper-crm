"""Nominations for the nominations officer: candidates, list, detail, nominate, status moves."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import AfterValidator

from backend.api.deps import NominationsOfficer, SessionDep
from backend.api.install import PartyOnlyRoute
from backend.api.reads import aspirant_read
from backend.models import AspirantStatus, Seat
from backend.schemas.admin import AdminUserCreated
from backend.schemas.aspirants import (
    AspirantCreate,
    AspirantMove,
    AspirantPage,
    AspirantRead,
    CandidateRead,
    WorkspaceCreate,
    WorkspaceCreated,
)
from backend.schemas.common import plain_text
from backend.services import aspirants
from backend.services.aspirants import AspirantFilters

router = APIRouter(prefix="/party/aspirants", tags=["party"], route_class=PartyOnlyRoute)


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
    return AspirantPage(total=total, items=[aspirant_read(row) for row in rows])


@router.get("/{aspirant_id}/", response_model=AspirantRead)
async def get_aspirant(
    aspirant_id: uuid.UUID, user: NominationsOfficer, session: SessionDep
) -> AspirantRead:
    return aspirant_read(await aspirants.get_aspirant(session, aspirant_id))


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
    return aspirant_read(await aspirants.get_aspirant(session, created.id))


@router.post("/{aspirant_id}/status/", response_model=AspirantRead)
async def move_aspirant(
    aspirant_id: uuid.UUID, payload: AspirantMove, user: NominationsOfficer, session: SessionDep
) -> AspirantRead:
    """Move a nomination along the table; rejecting and suspending need a reason."""
    aspirant = await aspirants.get_aspirant(session, aspirant_id)
    await aspirants.move(session, aspirant, payload.status, actor=user, reason=payload.reason)
    await session.commit()
    return aspirant_read(await aspirants.get_aspirant(session, aspirant_id))


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
        aspirant=aspirant_read(await aspirants.get_aspirant(session, aspirant_id)),
        setup=summary,
        logins=[AdminUserCreated.of(login, invite) for login, invite in logins],
    )
