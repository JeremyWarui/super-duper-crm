"""A campaign's own team: who is on it, and the aspirant setting the manager."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from backend.api.deps import SessionDep, TeamWriter, require_role
from backend.api.scope import require_visible_campaign
from backend.models import User, UserRole
from backend.schemas.team import ManagerCreate, ManagerCreated, TeamMemberRead
from backend.services import team

router = APIRouter(prefix="/campaigns/{campaign_id}/team", tags=["team"])

Aspirant = Annotated[
    User,
    Depends(
        require_role(
            UserRole.CANDIDATE, message="Only the aspirant adds or replaces the campaign manager."
        )
    ),
]


@router.get("/", response_model=list[TeamMemberRead])
async def list_team(campaign_id: uuid.UUID, session: SessionDep, user: TeamWriter) -> list[User]:
    await require_visible_campaign(session, user, campaign_id)
    return await team.team(session, campaign_id)


@router.post("/manager/", response_model=ManagerCreated, status_code=status.HTTP_201_CREATED)
async def set_manager(
    campaign_id: uuid.UUID, payload: ManagerCreate, session: SessionDep, user: Aspirant
) -> ManagerCreated:
    """Add the campaign's manager, or replace the one it has; the password is shown once."""
    campaign = await require_visible_campaign(session, user, campaign_id)
    created, password, replaced = await team.set_manager(
        session,
        campaign,
        payload.model_dump(exclude={"replace"}),
        replace=payload.replace,
        actor=user,
    )
    return ManagerCreated(
        id=created.id,
        username=created.username,
        full_name=created.full_name,
        password=password,
        replaced=replaced,
    )
