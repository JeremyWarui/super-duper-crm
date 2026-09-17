"""Campaigns, and the one call that stands a new one up."""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.api.deps import CurrentUser, SessionDep, Writer
from backend.api.scope import (
    add_member,
    limit_to_campaigns,
    require_visible_campaign,
    visible_campaign_ids,
    visible_user_ids,
)
from backend.models import Campaign, OfficeLevel, User, UserRole
from backend.schemas.campaign import (
    CampaignRead,
    CampaignSetup,
    CampaignSetupResponse,
    CandidateLogin,
    NewCandidate,
    SetupSummary,
)
from backend.security import hash_password, new_password
from backend.services.targets import generate_targets

router = APIRouter(prefix="/campaigns", tags=["campaigns"])

AREA_FIELD = {
    OfficeLevel.COUNTY: "county",
    OfficeLevel.CONSTITUENCY: "constituency",
    OfficeLevel.WARD: "ward",
}


# Who a campaign is for and where it is fought live in other tables, so every
# read that names it loads these four and nothing else lazily.
NAMED = (
    selectinload(Campaign.candidate),
    selectinload(Campaign.county),
    selectinload(Campaign.constituency),
    selectinload(Campaign.ward),
)


def _named(campaign: Campaign) -> CampaignRead:
    """A campaign with its candidate and its seat spelt out."""
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
    """The caller's campaigns."""
    statement = select(Campaign).options(*NAMED).order_by(Campaign.created_at)
    visible = await visible_campaign_ids(session, user)
    statement = limit_to_campaigns(statement, Campaign.id, visible)
    return [_named(c) for c in (await session.execute(statement)).scalars()]


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

    candidate_id, login = await _resolve_candidate(session, user, payload)

    area_field = AREA_FIELD[payload.office_level]
    area_id = getattr(payload, area_field)
    if area_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"A {payload.office_level.label} campaign needs its {area_field} set.",
        )

    campaign = Campaign(
        title=payload.title,
        office_level=payload.office_level,
        election_date=payload.election_date,
        **{f"{area_field}_id": area_id},
    )
    session.add(campaign)
    await session.flush()

    # The candidate is on their own campaign, and whoever set it up is on it too.
    await add_member(session, campaign.id, candidate_id)
    if user.id != candidate_id:
        await add_member(session, campaign.id, user.id)
    await session.commit()

    summary = await generate_targets(session, campaign)
    # Reloaded with its people and its place, so the reply names them the same
    # way every later read does.
    campaign = (
        await session.execute(select(Campaign).options(*NAMED).where(Campaign.id == campaign.id))
    ).scalar_one()
    return CampaignSetupResponse(
        **_named(campaign).model_dump(),
        setup=SetupSummary.model_validate(summary),
        candidate_login=login,
    )


async def _resolve_candidate(
    session: SessionDep, user: User, payload: CampaignSetup
) -> tuple[uuid.UUID, CandidateLogin | None]:
    """Whose campaign this is, and the login if one was created for them.

    A candidate gets themselves. A manager must name an aspirant or create one:
    inferring it from whoever filled the form in is how a campaign ends up owned
    by its manager and invisible to its candidate.
    """
    if user.role is UserRole.CANDIDATE:
        if payload.new_candidate is not None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "You are the candidate; do not create another."
            )
        if payload.candidate is not None and payload.candidate != user.id:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "A candidate may only set up their own campaign."
            )
        return user.id, None

    if payload.new_candidate is not None:
        if payload.candidate is not None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Name an existing aspirant or create one, not both.",
            )
        return await _create_candidate(session, payload.new_candidate)

    if payload.candidate is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Say who this campaign is for: name an aspirant, or create one.",
        )

    visible = await visible_user_ids(session, user)
    if payload.candidate not in visible:
        # Same answer as a name that does not exist, so the field cannot be used
        # to enumerate aspirants the caller has no business with.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No such aspirant.")

    aspirant = await session.get(User, payload.candidate)
    if aspirant is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No such aspirant.")
    if aspirant.role is not UserRole.CANDIDATE:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{aspirant.username} is not an aspirant.")
    return aspirant.id, None


async def _create_candidate(
    session: SessionDep, details: NewCandidate
) -> tuple[uuid.UUID, CandidateLogin]:
    taken = (
        await session.execute(select(User).where(User.username == details.username))
    ).scalar_one_or_none()
    if taken is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"The username {details.username} is already taken."
        )

    password = new_password()
    aspirant = User(
        username=details.username,
        role=UserRole.CANDIDATE,
        first_name=details.first_name,
        last_name=details.last_name,
        phone=details.phone,
        email=details.email,
        password_hash=hash_password(password),
    )
    session.add(aspirant)
    await session.flush()
    return aspirant.id, CandidateLogin(
        id=aspirant.id,
        username=aspirant.username,
        full_name=aspirant.full_name,
        password=password,
    )


@router.get("/{campaign_id}/", response_model=CampaignRead)
async def get_campaign(
    campaign_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> CampaignRead:
    await require_visible_campaign(session, user, campaign_id)
    found = (
        await session.execute(select(Campaign).options(*NAMED).where(Campaign.id == campaign_id))
    ).scalar_one()
    return _named(found)


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
