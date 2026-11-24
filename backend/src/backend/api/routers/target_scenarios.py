"""Trying a turnout scenario, setting one for the team (`services/target_scenarios.py`), and the
notices that tell people their target changed."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select, update

from backend.api.deps import CurrentUser, SessionDep, require
from backend.api.scope import require_visible_campaign
from backend.models import Notice, TurnoutScenario, User
from backend.schemas.target_scenarios import (
    NoticeRead,
    ScenarioSet,
    ScenarioSetResult,
    TargetsPreview,
)
from backend.services import target_scenarios

router = APIRouter(tags=["targets"])

Previewer = Annotated[User, Depends(require("targets.preview"))]
Setter = Annotated[User, Depends(require("targets.set_scenario"))]


@router.get("/campaigns/{campaign_id}/targets/preview/", response_model=TargetsPreview)
async def preview(
    campaign_id: uuid.UUID,
    session: SessionDep,
    user: Previewer,
    scenario: TurnoutScenario | None = None,
    county: uuid.UUID | None = None,
) -> dict:
    """The seat and its units under a scenario, beside what the team works to; saves nothing."""
    campaign = await require_visible_campaign(session, user, campaign_id)
    return await target_scenarios.preview(
        session, campaign, scenario or campaign.turnout_scenario, county=county
    )


@router.post("/campaigns/{campaign_id}/targets/scenario/", response_model=ScenarioSetResult)
async def set_scenario(
    campaign_id: uuid.UUID, payload: ScenarioSet, session: SessionDep, user: Setter
) -> dict:
    """Set the scenario for the whole team; every target is saved again and the people whose
    target changed are told."""
    campaign = await require_visible_campaign(session, user, campaign_id)
    return await target_scenarios.set_scenario(session, campaign, payload.scenario, actor=user)


@router.get("/notices/", response_model=list[NoticeRead])
async def notices(session: SessionDep, user: CurrentUser) -> list:
    """The caller's unread notices, newest first."""
    return list(
        await session.scalars(
            select(Notice)
            .where(Notice.user_id == user.id, Notice.read_at.is_(None))
            .order_by(Notice.created_at.desc())
            .limit(20)
        )
    )


@router.post("/notices/{notice_id}/read/", status_code=status.HTTP_204_NO_CONTENT)
async def read_notice(notice_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> None:
    await session.execute(
        update(Notice)
        .where(Notice.id == notice_id, Notice.user_id == user.id)
        .values(read_at=datetime.now(UTC))
    )
    await session.commit()
