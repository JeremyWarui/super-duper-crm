"""The computed strategy read."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from backend.api.deps import SessionDep, require
from backend.api.scope import area_of, visible_campaign_ids
from backend.models import User
from backend.schemas.strategy import StrategyRead
from backend.services.strategy import read_strategy

router = APIRouter(tags=["strategy"])
Reader = Annotated[User, Depends(require("strategy.read"))]


@router.get("/strategy/", response_model=StrategyRead)
async def get_strategy(
    session: SessionDep,
    user: Reader,
    campaign: uuid.UUID | None = None,
    county: uuid.UUID | None = None,
    constituency: uuid.UUID | None = None,
) -> StrategyRead:
    """The win number and notes over every unit the caller reaches; the units themselves only
    in `county` or `constituency` when given, and none unasked for a national seat."""
    return await read_strategy(
        session,
        campaign_ids=await visible_campaign_ids(session, user),
        campaign_id=campaign,
        area=await area_of(session, user, "strategy.read"),
        county=county,
        constituency=constituency,
    )
