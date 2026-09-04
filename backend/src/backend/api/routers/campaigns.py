"""Campaigns, and the one call that stands a new one up."""

import uuid

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from backend.api.deps import CurrentUser, SessionDep, Writer
from backend.api.scope import limit_to_campaigns, require_visible_campaign, visible_campaign_ids
from backend.models import Campaign, OfficeLevel, UserRole
from backend.schemas.campaign import (
    CampaignRead,
    CampaignSetup,
    CampaignSetupResponse,
    SetupSummary,
)
from backend.services.targets import generate_targets

router = APIRouter(prefix="/campaigns", tags=["campaigns"])

AREA_FIELD = {
    OfficeLevel.COUNTY: "county",
    OfficeLevel.CONSTITUENCY: "constituency",
    OfficeLevel.WARD: "ward",
}


@router.get("/", response_model=list[CampaignRead])
async def list_campaigns(session: SessionDep, user: CurrentUser) -> list[Campaign]:
    """The caller's campaigns."""
    statement = select(Campaign).order_by(Campaign.created_at)
    visible = await visible_campaign_ids(session, user)
    statement = limit_to_campaigns(statement, Campaign.id, visible)
    return list((await session.execute(statement)).scalars().all())


@router.post(
    "/setup/",
    response_model=CampaignSetupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def setup_campaign(
    payload: CampaignSetup, session: SessionDep, user: CurrentUser
) -> CampaignSetupResponse:
    """Create the campaign and every one of its targets in one call."""
    if user.role is UserRole.MOBILIZER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "A mobilizer may not create a campaign.")

    area_field = AREA_FIELD[payload.office_level]
    area_id = getattr(payload, area_field)
    if area_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"A {payload.office_level.label} campaign needs its {area_field} set.",
        )

    campaign = Campaign(
        candidate_id=user.id,
        title=payload.title,
        office_level=payload.office_level,
        election_date=payload.election_date,
        **{f"{area_field}_id": area_id},
    )
    session.add(campaign)
    await session.commit()

    summary = await generate_targets(session, campaign)
    return CampaignSetupResponse(
        **CampaignRead.model_validate(campaign).model_dump(),
        setup=SetupSummary.model_validate(summary),
    )


@router.get("/{campaign_id}/", response_model=CampaignRead)
async def get_campaign(campaign_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Campaign:
    return await require_visible_campaign(session, user, campaign_id)


@router.post("/{campaign_id}/generate_targets/", response_model=SetupSummary)
async def regenerate_targets(
    campaign_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    _: Writer,
) -> SetupSummary:
    """Rebuild the targets after new centres or wards are loaded."""
    campaign = await require_visible_campaign(session, user, campaign_id)
    summary = await generate_targets(session, campaign)
    return SetupSummary.model_validate(summary)


@router.delete("/{campaign_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    _: Writer,
) -> Response:
    """Removes the campaign and everything hanging off it."""
    campaign = await require_visible_campaign(session, user, campaign_id)
    await session.delete(campaign)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
