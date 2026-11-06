"""A hosted campaign's "From the party" page and its sharing switches (`services/sharing.py`)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.deps import SessionDep, Today, require
from backend.api.scope import require_visible_campaign
from backend.models import Campaign, User, WorkspaceKind
from backend.schemas.sharing import PartyFeed, Switches, SwitchesWrite
from backend.services import sharing
from backend.services.permissions import reach

router = APIRouter(prefix="/party-feed", tags=["party-feed"])

Reader = Annotated[User, Depends(require("party.feed"))]
Changer = Annotated[User, Depends(require("sharing.write"))]


async def _hosted(session, user: User, campaign_id: uuid.UUID) -> Campaign:
    """The caller's campaign when it is a hosted one; the party and standalone have no feed."""
    campaign = await require_visible_campaign(session, user, campaign_id)
    if campaign.kind is not WorkspaceKind.HOSTED:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Only a party nominee's workspace has this.")
    return campaign


@router.get("/", response_model=PartyFeed)
async def party_feed(campaign: uuid.UUID, session: SessionDep, user: Reader, today: Today) -> dict:
    found = await _hosted(session, user, campaign)
    return {
        **await sharing.feed(session, found, today),
        "sharing": await sharing.switches(session, found.id),
        "can_change": reach(user, "sharing.write") is not None,
        "history": await sharing.history(session, found.id),
    }


@router.put("/sharing/", response_model=Switches)
async def change_sharing(
    campaign: uuid.UUID, payload: SwitchesWrite, session: SessionDep, user: Changer
) -> dict:
    found = await _hosted(session, user, campaign)
    return await sharing.change(session, found, payload.model_dump(), actor=user)
