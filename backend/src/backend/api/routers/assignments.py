"""Assigning work to mobilizers and agents, and marking it done or cancelled."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from backend.api.deps import SessionDep, require
from backend.api.scope import area_of, own_ids, require_visible_campaign
from backend.db.session import get_or_refuse
from backend.models import Assignment, AssignmentStatus, User
from backend.schemas.assignment import AssignmentCreate, AssignmentRead
from backend.services import assignments
from backend.services.permissions import Reach, reach

router = APIRouter(prefix="/assignments", tags=["assignments"])

Reader = Annotated[User, Depends(require("assignments.read"))]
Writer = Annotated[User, Depends(require("assignments.write"))]


def _read(row: Assignment) -> AssignmentRead:
    if row.mobilizer is not None:
        name, role = row.mobilizer.full_name, "mobilizer"
    else:
        name, role = row.agent.user.display_name, "agent"
    return AssignmentRead(
        id=row.id,
        kind=row.kind,
        label=row.label,
        member_name=name,
        member_role=role,
        ward_name=row.ward.name if row.ward else None,
        centre_name=row.registration_centre.name if row.registration_centre else None,
        amount_kes=row.amount_kes,
        status=row.status,
        done_at=row.done_at,
        created_at=row.created_at,
    )


@router.get("/", response_model=list[AssignmentRead])
async def list_assignments(
    campaign: uuid.UUID,
    session: SessionDep,
    user: Reader,
    status: AssignmentStatus | None = None,
) -> list[AssignmentRead]:
    """The caller's assignments: all, a coordinator's area, or a mobilizer's or agent's own."""
    await require_visible_campaign(session, user, campaign)
    if reach(user, "assignments.read") is Reach.OWN:
        mobilizer_id, agent_id = await own_ids(session, user)
        rows = await assignments.assignments(
            session, campaign, None, mobilizer_id=mobilizer_id, agent_id=agent_id, status=status
        )
    else:
        area = await area_of(session, user, "assignments.read")
        rows = await assignments.assignments(session, campaign, area, status=status)
    return [_read(row) for row in rows]


@router.post("/", response_model=AssignmentRead, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    payload: AssignmentCreate, session: SessionDep, user: Writer
) -> AssignmentRead:
    campaign = await require_visible_campaign(session, user, payload.campaign)
    area = await area_of(session, user, "assignments.write")
    row = await assignments.create(
        session, campaign, payload.model_dump(exclude={"campaign"}), area, actor=user
    )
    return _read(row)


async def _settle(
    session: SessionDep, user: User, assignment_id: uuid.UUID, outcome: AssignmentStatus
) -> AssignmentRead:
    found = await get_or_refuse(session, Assignment, assignment_id, "assignment")
    campaign = await require_visible_campaign(session, user, found.campaign_id)
    area = await area_of(session, user, "assignments.write")
    row = await assignments.assignment(session, campaign.id, assignment_id, area)
    return _read(await assignments.settle(session, campaign, row, outcome, actor=user))


@router.post("/{assignment_id}/done/", response_model=AssignmentRead)
async def mark_done(assignment_id: uuid.UUID, session: SessionDep, user: Writer) -> AssignmentRead:
    """The work happened; it can now be paid for."""
    return await _settle(session, user, assignment_id, AssignmentStatus.DONE)


@router.post("/{assignment_id}/cancel/", response_model=AssignmentRead)
async def cancel(assignment_id: uuid.UUID, session: SessionDep, user: Writer) -> AssignmentRead:
    return await _settle(session, user, assignment_id, AssignmentStatus.CANCELLED)
