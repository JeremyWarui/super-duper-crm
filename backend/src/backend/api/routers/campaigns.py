"""Campaigns, and the one call that stands a new one up."""

import uuid

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from backend.api.deps import CurrentUser, SessionDep, Writer
from backend.api.scope import limit_to_campaigns, require_visible_campaign, visible_campaign_ids
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

    candidate_id, login = await _resolve_candidate(session, user, payload)

    area_field = AREA_FIELD[payload.office_level]
    area_id = getattr(payload, area_field)
    if area_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"A {payload.office_level.label} campaign needs its {area_field} set.",
        )

    campaign = Campaign(
        candidate_id=candidate_id,
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
