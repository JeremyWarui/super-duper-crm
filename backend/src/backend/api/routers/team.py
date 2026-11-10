"""A campaign's own team: who is on it, its manager, its coordinators and comms, and the
coordinators' areas."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from backend.api.deps import SessionDep, require
from backend.api.scope import require_visible_campaign
from backend.models import User
from backend.schemas.team import (
    AreaRead,
    AreaWrite,
    ManagerCreate,
    ManagerCreated,
    StaffCreate,
    StaffCreated,
    TeamMemberRead,
)
from backend.services import team

router = APIRouter(prefix="/campaigns/{campaign_id}/team", tags=["team"])

Aspirant = Annotated[User, Depends(require("team.manager"))]
TeamWriter = Annotated[User, Depends(require("team.write"))]


@router.get("/", response_model=list[TeamMemberRead])
async def list_team(campaign_id: uuid.UUID, session: SessionDep, user: TeamWriter) -> list[User]:
    await require_visible_campaign(session, user, campaign_id)
    return await team.team(session, campaign_id)


@router.post("/manager/", response_model=ManagerCreated, status_code=status.HTTP_201_CREATED)
async def set_manager(
    campaign_id: uuid.UUID, payload: ManagerCreate, session: SessionDep, user: Aspirant
) -> ManagerCreated:
    """Add the campaign's manager, or replace the one it has, and send them an invite link."""
    campaign = await require_visible_campaign(session, user, campaign_id)
    created, invite, replaced = await team.set_manager(
        session,
        campaign,
        payload.model_dump(exclude={"replace"}),
        replace=payload.replace,
        actor=user,
    )
    return ManagerCreated.of(created, invite, replaced=replaced)


@router.post("/", response_model=StaffCreated, status_code=status.HTTP_201_CREATED)
async def add_staff(
    campaign_id: uuid.UUID, payload: StaffCreate, session: SessionDep, user: TeamWriter
) -> StaffCreated:
    """Add a coordinator or comms officer and send them an invite link."""
    campaign = await require_visible_campaign(session, user, campaign_id)
    created, invite = await team.add_staff(
        session, campaign, payload.role, payload.model_dump(exclude={"role"}), actor=user
    )
    return StaffCreated.of(created, invite)


@router.delete("/{user_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def remove_staff(
    campaign_id: uuid.UUID, user_id: uuid.UUID, session: SessionDep, user: TeamWriter
) -> None:
    """Take a coordinator or comms officer off the campaign and turn their login off."""
    campaign = await require_visible_campaign(session, user, campaign_id)
    await team.remove_staff(session, campaign, user_id, actor=user)


@router.get("/{user_id}/area/", response_model=AreaRead)
async def read_area(
    campaign_id: uuid.UUID, user_id: uuid.UUID, session: SessionDep, user: TeamWriter
) -> AreaRead:
    await require_visible_campaign(session, user, campaign_id)
    wards, centres = await team.areas(session, campaign_id, user_id)
    return AreaRead(wards=wards, registration_centres=centres)


@router.put("/{user_id}/area/", response_model=AreaRead)
async def set_area(
    campaign_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: AreaWrite,
    session: SessionDep,
    user: TeamWriter,
) -> AreaRead:
    """Replace a coordinator's wards and registration centres."""
    campaign = await require_visible_campaign(session, user, campaign_id)
    wards, centres = await team.set_areas(
        session, campaign, user_id, payload.wards, payload.registration_centres, actor=user
    )
    return AreaRead(wards=wards, registration_centres=centres)
