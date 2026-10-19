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
from backend.models import Campaign, CampaignMember, Mobilizer, User, UserRole, Ward
from backend.schemas.campaign import MobilizerCreate, MobilizerRead, MobilizerUpdate
from backend.services.accounts import add_mobilizer, move_mobilizer

router = APIRouter(prefix="/mobilizers", tags=["mobilizers"])

LOADED = (selectinload(Mobilizer.ward),)


@router.get("/", response_model=list[MobilizerRead])
async def list_mobilizers(
    session: SessionDep, user: CurrentUser, campaign: uuid.UUID | None = None
) -> list[Mobilizer]:
    statement = await scoped(session, user, select(Mobilizer).options(*LOADED), Mobilizer, campaign)
    statement = statement.outerjoin(Ward, Mobilizer.ward_id == Ward.id)
    return await all_rows(session, statement.order_by(Ward.name.nulls_last(), Mobilizer.full_name))


@router.post("/", response_model=MobilizerRead, status_code=status.HTTP_201_CREATED)
async def create_mobilizer(
    payload: MobilizerCreate, session: SessionDep, user: TeamWriter
) -> Mobilizer:
    """Add somebody to the campaign, on a free ward or none, optionally with a login."""
    campaign = await require_visible_campaign(session, user, payload.campaign)
    await require_ward_in_campaign(session, campaign, payload.ward, payload.registration_centre)
    login = await _free_mobilizer(session, payload.user) if payload.user is not None else None
    mobilizer = await add_mobilizer(
        session,
        campaign,
        payload.ward,
        login,
        centre_id=payload.registration_centre,
        full_name=payload.full_name,
        phone=payload.phone,
    )
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


@router.patch("/{mobilizer_id}/", response_model=MobilizerRead)
async def update_mobilizer(
    mobilizer_id: uuid.UUID, payload: MobilizerUpdate, session: SessionDep, user: TeamWriter
) -> Mobilizer:
    """Rename, or move to a unit or to none; whoever held that unit is left unassigned."""
    mobilizer = await require_visible(session, user, Mobilizer, mobilizer_id, "mobilizer")
    fields = payload.model_dump(exclude_unset=True)
    if "ward" in fields or "registration_centre" in fields:
        # A field left out keeps its value; a new ward without a centre drops the old centre.
        ward_id = fields.get("ward", mobilizer.ward_id)
        if "registration_centre" in fields:
            centre_id = fields["registration_centre"]
        else:
            centre_id = None if "ward" in fields else mobilizer.registration_centre_id
        campaign = await session.get(Campaign, mobilizer.campaign_id)
        await require_ward_in_campaign(session, campaign, ward_id, centre_id)
        await move_mobilizer(session, campaign, mobilizer, ward_id, centre_id)
    for name in ("full_name", "phone"):
        if fields.get(name) is not None:
            setattr(mobilizer, name, fields[name])
    await session.commit()
    return await load(session, Mobilizer, mobilizer.id, LOADED)


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
