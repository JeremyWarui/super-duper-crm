"""The computed strategy read."""

import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from backend.api.deps import CurrentUser, SessionDep, mobilizer_ward_id
from backend.api.scope import visible_campaign_ids
from backend.services.strategy import read_strategy

router = APIRouter(tags=["strategy"])


class UnitRead(BaseModel):
    unit: str
    needed: int
    committed: int
    gap: int
    progress: float
    events: int
    has_mobilizer: bool
    share: float


class NoteRead(BaseModel):
    tone: str
    title: str
    text: str


class StrategyRead(BaseModel):
    win_number: int
    committed: int
    progress_pct: float
    total_registered: int
    total_cast: int
    units: list[UnitRead]
    notes: list[NoteRead]


@router.get("/strategy/", response_model=StrategyRead)
async def get_strategy(
    session: SessionDep, user: CurrentUser, campaign: uuid.UUID | None = None
) -> object:
    return await read_strategy(
        session,
        campaign_ids=await visible_campaign_ids(session, user),
        campaign_id=campaign,
        ward_id=mobilizer_ward_id(user),
    )
