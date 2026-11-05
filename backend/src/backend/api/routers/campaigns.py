"""Campaigns: reading them, rebuilding their targets, and the volunteers their candidate's
website page signed up."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.api.deps import CurrentUser, SessionDep, require
from backend.api.scope import (
    all_rows,
    area_of,
    load,
    require_visible_campaign,
    visible_campaign_ids,
)
from backend.models import Campaign, User, VolunteerProfile, VolunteerStatus, WorkspaceKind
from backend.schemas.campaign import CampaignRead, CampaignSignups, EventSignups, SetupSummary
from backend.schemas.candidates import CampaignVolunteerRead, CampaignVolunteerUpdate
from backend.services import campaign_volunteers, site
from backend.services.targets import generate_targets

router = APIRouter(prefix="/campaigns", tags=["campaigns"])
# The campaign-wide sign-up link reaches the whole register.
SignupsWriter = Annotated[User, Depends(require("supporters.write", whole=True))]
TargetsWriter = Annotated[User, Depends(require("targets.write"))]
VolunteerReader = Annotated[User, Depends(require("volunteers.read"))]
VolunteerWriter = Annotated[User, Depends(require("volunteers.write"))]

NAMED = (
    selectinload(Campaign.candidate),
    selectinload(Campaign.county),
    selectinload(Campaign.constituency),
    selectinload(Campaign.ward),
)


async def _named(session: SessionDep, campaign: Campaign) -> CampaignRead:
    """A campaign with its candidate and seat spelt out, the party's name standing for the
    candidate of the party workspace; needs NAMED loaded."""
    area = campaign.area
    candidate = campaign.candidate
    name = (candidate.full_name or candidate.username) if candidate else ""
    if campaign.kind is WorkspaceKind.PARTY:
        name = (await site.read_settings(session)).name
    return CampaignRead.model_validate(campaign).model_copy(
        update={
            "candidate_name": name,
            "candidate_username": candidate.username if candidate else "",
            "seat": campaign.seat_label,
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
    return [await _named(session, c) for c in await all_rows(session, statement)]


@router.get("/{campaign_id}/", response_model=CampaignRead)
async def get_campaign(
    campaign_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> CampaignRead:
    await require_visible_campaign(session, user, campaign_id)
    return await _named(session, await load(session, Campaign, campaign_id, NAMED))


@router.get("/{campaign_id}/signups/", response_model=CampaignSignups)
async def read_signups(
    campaign_id: uuid.UUID, session: SessionDep, user: SignupsWriter
) -> CampaignSignups:
    """The campaign-wide sign-up link, to share."""
    campaign = await require_visible_campaign(session, user, campaign_id)
    return CampaignSignups(code=campaign.signup_code, open=campaign.signups_open)


@router.post("/{campaign_id}/signups/", response_model=CampaignSignups)
async def set_signups(
    campaign_id: uuid.UUID, payload: EventSignups, session: SessionDep, user: SignupsWriter
) -> CampaignSignups:
    """Open or close the campaign-wide sign-up link."""
    campaign = await require_visible_campaign(session, user, campaign_id)
    campaign.signups_open = payload.open
    await session.commit()
    return CampaignSignups(code=campaign.signup_code, open=campaign.signups_open)


@router.post("/{campaign_id}/generate_targets/", response_model=SetupSummary)
async def regenerate_targets(
    campaign_id: uuid.UUID, session: SessionDep, user: TargetsWriter
) -> SetupSummary:
    """Rebuild the targets after new centres or wards are loaded."""
    summary = await generate_targets(
        session, await require_visible_campaign(session, user, campaign_id)
    )
    await session.commit()
    return summary


@router.get("/{campaign_id}/volunteers/", response_model=list[CampaignVolunteerRead])
async def list_volunteers(
    campaign_id: uuid.UUID,
    session: SessionDep,
    user: VolunteerReader,
    q: Annotated[str, Query(max_length=100)] = "",
    ward: uuid.UUID | None = None,
    volunteer_status: Annotated[VolunteerStatus | None, Query(alias="status")] = None,
) -> list[VolunteerProfile]:
    """The volunteers the candidate's website page signed up, newest first."""
    await require_visible_campaign(session, user, campaign_id)
    return await campaign_volunteers.volunteers(
        session,
        campaign_id,
        q=q,
        ward=ward,
        status=volunteer_status,
        area=await area_of(session, user, "volunteers.read"),
    )


@router.patch("/{campaign_id}/volunteers/{volunteer_id}/", response_model=CampaignVolunteerRead)
async def update_volunteer(
    campaign_id: uuid.UUID,
    volunteer_id: uuid.UUID,
    payload: CampaignVolunteerUpdate,
    session: SessionDep,
    user: VolunteerWriter,
) -> VolunteerProfile:
    """Make a volunteer active or inactive, and edit the notes about them."""
    await require_visible_campaign(session, user, campaign_id)
    return await campaign_volunteers.update_volunteer(
        session,
        campaign_id,
        volunteer_id,
        payload,
        actor=user,
        area=await area_of(session, user, "volunteers.write"),
    )
