"""Campaigns: reading them, setting one up, and rebuilding its targets."""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.api.deps import CurrentUser, SessionDep, Writer
from backend.api.scope import all_rows, load, require_visible_campaign, visible_campaign_ids
from backend.models import Campaign, OfficeLevel, User, UserRole
from backend.schemas.campaign import (
    CampaignRead,
    CampaignSetup,
    CampaignSetupResponse,
    SetupSummary,
)
from backend.schemas.common import NewLogin
from backend.services.accounts import add_member, campaign_of, new_login
from backend.services.targets import generate_targets

router = APIRouter(prefix="/campaigns", tags=["campaigns"])

AREA_FIELD = {
    OfficeLevel.COUNTY: "county",
    OfficeLevel.CONSTITUENCY: "constituency",
    OfficeLevel.WARD: "ward",
}

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
            "seat": campaign.office_level.label,
            "area_name": area.name if area is not None else "",
        }
    )


@router.get("/", response_model=list[CampaignRead])
async def list_campaigns(session: SessionDep, user: CurrentUser) -> list[CampaignRead]:
    """The caller's campaign, in a list; empty sends them to setup."""
    statement = (
        select(Campaign)
        .options(*NAMED)
        .where(Campaign.id.in_(await visible_campaign_ids(session, user)))
        .order_by(Campaign.created_at)
    )
    return [_named(c) for c in await all_rows(session, statement)]


@router.post("/setup/", response_model=CampaignSetupResponse, status_code=status.HTTP_201_CREATED)
async def setup_campaign(
    payload: CampaignSetup, session: SessionDep, user: CurrentUser
) -> CampaignSetupResponse:
    """Create a campaign for its candidate, and every one of its targets."""
    if user.role is UserRole.MOBILIZER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "A mobilizer may not create a campaign.")
    current = await campaign_of(session, user.id)
    if current is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"You are already on {current.title}; a login belongs to one campaign.",
        )

    area_field = AREA_FIELD[payload.office_level]
    area_id = getattr(payload, area_field)
    if area_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"A {payload.office_level.label} campaign needs its {area_field} set.",
        )
    candidate, login = await _candidate(session, user, payload)

    campaign = Campaign(
        title=payload.title,
        office_level=payload.office_level,
        election_date=payload.election_date,
        **{f"{area_field}_id": area_id},
    )
    session.add(campaign)
    await session.flush()
    await add_member(session, campaign.id, candidate)
    if user.id != candidate.id:
        await add_member(session, campaign.id, user)
    summary = await generate_targets(session, campaign)
    await session.commit()

    return CampaignSetupResponse(
        **_named(await load(session, Campaign, campaign.id, NAMED)).model_dump(),
        setup=summary,
        candidate_login=login,
    )


async def _candidate(
    session: SessionDep, user: User, payload: CampaignSetup
) -> tuple[User, NewLogin | None]:
    """A candidate sets up their own campaign; a manager creates the aspirant's login."""
    if user.role is UserRole.CANDIDATE:
        if payload.new_candidate is not None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "You are the candidate; do not create another."
            )
        return user, None
    if payload.new_candidate is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Say who this campaign is for: create the aspirant's login.",
        )
    details = payload.new_candidate
    aspirant, password = await new_login(session, role=UserRole.CANDIDATE, **details.model_dump())
    return aspirant, NewLogin(
        id=aspirant.id, username=aspirant.username, full_name=aspirant.full_name, password=password
    )


@router.get("/{campaign_id}/", response_model=CampaignRead)
async def get_campaign(
    campaign_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> CampaignRead:
    await require_visible_campaign(session, user, campaign_id)
    return _named(await load(session, Campaign, campaign_id, NAMED))


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
