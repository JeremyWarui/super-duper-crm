"""Campaigns: reading them, rebuilding their targets, and the volunteers their candidate's
website page signed up."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from backend.api.deps import CurrentUser, SessionDep, require
from backend.api.scope import (
    VisibleCampaign,
    all_rows,
    area_of,
    load,
    visible_campaign_ids,
)
from backend.models import Campaign, User, VolunteerProfile, VolunteerStatus, WorkspaceKind
from backend.schemas.campaign import CampaignRead, CampaignSignups, EventSignups, SetupSummary
from backend.schemas.candidates import CampaignVolunteerRead, CampaignVolunteerUpdate
from backend.services import campaign_volunteers, site
from backend.services.campaigns import CAMPAIGN_NAMES
from backend.services.targets import refresh_targets

router = APIRouter(prefix="/campaigns", tags=["campaigns"])
# The campaign-wide sign-up link reaches the whole register.
SignupsWriter = Annotated[User, Depends(require("supporters.write", whole=True))]
TargetsWriter = Annotated[User, Depends(require("targets.write"))]
VolunteerReader = Annotated[User, Depends(require("volunteers.read"))]
VolunteerWriter = Annotated[User, Depends(require("volunteers.write"))]


async def _named(session: SessionDep, campaign: Campaign) -> CampaignRead:
    """A campaign with its candidate and seat spelt out, the party's name standing for the
    candidate of the party workspace; needs CAMPAIGN_NAMES loaded."""
    area = campaign.area
    candidate = campaign.candidate
    name = campaign.candidate_label
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
        .options(*CAMPAIGN_NAMES)
        .where(Campaign.id.in_(await visible_campaign_ids(session, user)))
        .order_by(Campaign.created_at)
    )
    return [await _named(session, c) for c in await all_rows(session, statement)]


@router.get("/{campaign_id}/", response_model=CampaignRead)
async def get_campaign(
    session: SessionDep, user: CurrentUser, campaign: VisibleCampaign
) -> CampaignRead:
    return await _named(session, await load(session, Campaign, campaign.id, CAMPAIGN_NAMES))


@router.get("/{campaign_id}/signups/", response_model=CampaignSignups)
async def read_signups(
    session: SessionDep, user: SignupsWriter, campaign: VisibleCampaign
) -> CampaignSignups:
    """The campaign-wide sign-up link, to share."""
    return CampaignSignups(code=campaign.signup_code, open=campaign.signups_open)


@router.post("/{campaign_id}/signups/", response_model=CampaignSignups)
async def set_signups(
    payload: EventSignups, session: SessionDep, user: SignupsWriter, campaign: VisibleCampaign
) -> CampaignSignups:
    """Open or close the campaign-wide sign-up link."""
    campaign.signups_open = payload.open
    await session.commit()
    return CampaignSignups(code=campaign.signup_code, open=campaign.signups_open)


@router.post("/{campaign_id}/generate_targets/", response_model=SetupSummary)
async def regenerate_targets(
    session: SessionDep, user: TargetsWriter, campaign: VisibleCampaign
) -> SetupSummary:
    """Rebuild the targets after new centres or wards are loaded, as Refresh targets does."""
    return await refresh_targets(session, campaign, actor=user)


@router.get("/{campaign_id}/volunteers/", response_model=list[CampaignVolunteerRead])
async def list_volunteers(
    session: SessionDep,
    user: VolunteerReader,
    campaign: VisibleCampaign,
    q: Annotated[str, Query(max_length=100)] = "",
    ward: uuid.UUID | None = None,
    volunteer_status: Annotated[VolunteerStatus | None, Query(alias="status")] = None,
) -> list[VolunteerProfile]:
    """The volunteers the candidate's website page signed up, newest first."""
    return await campaign_volunteers.volunteers(
        session,
        campaign.id,
        q=q,
        ward=ward,
        status=volunteer_status,
        area=await area_of(session, user, "volunteers.read"),
    )


@router.patch("/{campaign_id}/volunteers/{volunteer_id}/", response_model=CampaignVolunteerRead)
async def update_volunteer(
    volunteer_id: uuid.UUID,
    payload: CampaignVolunteerUpdate,
    session: SessionDep,
    user: VolunteerWriter,
    campaign: VisibleCampaign,
) -> VolunteerProfile:
    """Make a volunteer active or inactive, and edit the notes about them."""
    return await campaign_volunteers.update_volunteer(
        session,
        campaign.id,
        volunteer_id,
        payload,
        actor=user,
        area=await area_of(session, user, "volunteers.write"),
    )
