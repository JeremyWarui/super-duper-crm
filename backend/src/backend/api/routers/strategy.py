"""The computed strategy read."""

import uuid

from fastapi import APIRouter

from backend.api.deps import CurrentUser, SessionDep
from backend.api.scope import mobilizer_ward_id, visible_campaign_ids
from backend.schemas.strategy import StrategyRead
from backend.services.strategy import read_strategy

router = APIRouter(tags=["strategy"])


@router.get("/strategy/", response_model=StrategyRead)
async def get_strategy(
    session: SessionDep, user: CurrentUser, campaign: uuid.UUID | None = None
) -> StrategyRead:
    return await read_strategy(
        session,
        campaign_ids=await visible_campaign_ids(session, user),
        campaign_id=campaign,
        ward_id=mobilizer_ward_id(user),
    )
