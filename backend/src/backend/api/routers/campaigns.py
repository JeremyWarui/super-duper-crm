"""Campaigns: reading them and rebuilding their targets."""

import uuid

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.api.deps import CurrentUser, SessionDep, Writer
from backend.api.scope import all_rows, load, require_visible_campaign, visible_campaign_ids
from backend.models import Campaign
from backend.schemas.campaign import CampaignRead, CampaignSignups, EventSignups, SetupSummary
from backend.services.targets import generate_targets

router = APIRouter(prefix="/campaigns", tags=["campaigns"])

NAMED = (
    selectinload(Campaign.candidate),
    selectinload(Campaign.county),
    selectinload(Campaign.constituency),
    selectinload(Campaign.ward),
)


def _named(campaign: Campaign) -> CampaignRead:
    """A campaign with its candidate and seat spelt out; needs NAMED loaded."""
    area = campaign.area
    candidate = campaign.candidate
    return CampaignRead.model_validate(campaign).model_copy(
        update={
            "candidate_name": (candidate.full_name or candidate.username) if candidate else "",
            "candidate_username": candidate.username if candidate else "",
            "seat": f"{campaign.seat.label} seat",
            "area_name": area.name if area is not None else "",
        }
    )


@router.get("/", response_model=list[CampaignRead])
async def list_campaigns(session: SessionDep, user: CurrentUser) -> list[CampaignRead]:
    """The caller's campaign, in a list; empty when they are on none."""
    statement = (
        select(Campaign)
        .options(*NAMED)
        .where(Campaign.id.in_(await visible_campaign_ids(session, user)))
        .order_by(Campaign.created_at)
    )
    return [_named(c) for c in await all_rows(session, statement)]


@router.get("/{campaign_id}/", response_model=CampaignRead)
async def get_campaign(
    campaign_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> CampaignRead:
    await require_visible_campaign(session, user, campaign_id)
    return _named(await load(session, Campaign, campaign_id, NAMED))


@router.get("/{campaign_id}/signups/", response_model=CampaignSignups)
async def read_signups(
    campaign_id: uuid.UUID, session: SessionDep, user: Writer
) -> CampaignSignups:
    """The campaign-wide sign-up link, for the manager to share."""
    campaign = await require_visible_campaign(session, user, campaign_id)
    return CampaignSignups(code=campaign.signup_code, open=campaign.signups_open)


@router.post("/{campaign_id}/signups/", response_model=CampaignSignups)
async def set_signups(
    campaign_id: uuid.UUID, payload: EventSignups, session: SessionDep, user: Writer
) -> CampaignSignups:
    """Open or close the campaign-wide sign-up link."""
    campaign = await require_visible_campaign(session, user, campaign_id)
    campaign.signups_open = payload.open
    await session.commit()
    return CampaignSignups(code=campaign.signup_code, open=campaign.signups_open)


@router.post("/{campaign_id}/generate_targets/", response_model=SetupSummary)
async def regenerate_targets(
    campaign_id: uuid.UUID, session: SessionDep, user: Writer
) -> SetupSummary:
    """Rebuild the targets after new centres or wards are loaded."""
    summary = await generate_targets(
        session, await require_visible_campaign(session, user, campaign_id)
    )
    await session.commit()
    return summary
