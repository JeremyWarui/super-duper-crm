"""The ground team: who works which ward."""

import uuid

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from backend.api.deps import CurrentUser, SessionDep, TeamWriter
from backend.api.scope import (
    all_rows,
    load,
    require_visible,
    require_visible_campaign,
    require_ward_in_campaign,
    scoped,
)
from backend.models import CampaignMember, Mobilizer, User, UserRole, Ward
from backend.schemas.campaign import MobilizerCreate, MobilizerRead
from backend.services.accounts import add_member

router = APIRouter(prefix="/mobilizers", tags=["mobilizers"])

LOADED = (selectinload(Mobilizer.ward),)


@router.get("/", response_model=list[MobilizerRead])
async def list_mobilizers(
    session: SessionDep, user: CurrentUser, campaign: uuid.UUID | None = None
) -> list[Mobilizer]:
    statement = await scoped(session, user, select(Mobilizer).options(*LOADED), Mobilizer, campaign)
    statement = statement.join(Ward, Mobilizer.ward_id == Ward.id)
    return await all_rows(session, statement.order_by(Ward.name, Mobilizer.full_name))


@router.post("/", response_model=MobilizerRead, status_code=status.HTTP_201_CREATED)
async def create_mobilizer(
    payload: MobilizerCreate, session: SessionDep, user: TeamWriter
) -> Mobilizer:
    """Put somebody on a ward, optionally tied to a mobilizer login that has no ground row yet."""
    campaign = await require_visible_campaign(session, user, payload.campaign)
    await require_ward_in_campaign(session, campaign, payload.ward, payload.registration_centre)
    if payload.user is not None:
        await add_member(session, campaign.id, await _free_mobilizer(session, payload.user))

    mobilizer = Mobilizer(
        campaign_id=payload.campaign,
        ward_id=payload.ward,
        registration_centre_id=payload.registration_centre,
        user_id=payload.user,
        full_name=payload.full_name,
        phone=payload.phone,
    )
    session.add(mobilizer)
    await session.commit()
    return await load(session, Mobilizer, mobilizer.id, LOADED)


async def _free_mobilizer(session: SessionDep, user_id: uuid.UUID) -> User:
    """A mobilizer login with no ground row yet; 400 or 409 otherwise."""
    named = await session.get(User, user_id)
    if named is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No such user.")
    if named.role is not UserRole.MOBILIZER:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{named.username} is not a mobilizer.")
    if await session.scalar(select(Mobilizer.id).where(Mobilizer.user_id == user_id)) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"{named.username} is already on the ground somewhere."
        )
    return named


@router.delete("/{mobilizer_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mobilizer(
    mobilizer_id: uuid.UUID, session: SessionDep, user: TeamWriter
) -> Response:
    """Take somebody off the ground, and their login off the campaign."""
    mobilizer = await require_visible(session, user, Mobilizer, mobilizer_id, "mobilizer")
    if mobilizer.user_id is not None:
        await session.execute(
            delete(CampaignMember).where(
                CampaignMember.campaign_id == mobilizer.campaign_id,
                CampaignMember.user_id == mobilizer.user_id,
            )
        )
    await session.delete(mobilizer)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
