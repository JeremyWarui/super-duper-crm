"""Ground organizers: who is working which ward."""

import uuid

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.api.deps import CurrentUser, SessionDep, Writer, mobilizer_ward_id
from backend.api.scope import (
    limit_to_campaigns,
    require_own_ward,
    require_visible_campaign,
    visible_campaign_ids,
)
from backend.models import Mobilizer, Ward
from backend.schemas.campaign import MobilizerCreate, MobilizerRead

router = APIRouter(prefix="/mobilizers", tags=["mobilizers"])

LOADED = (selectinload(Mobilizer.ward),)


@router.get("/", response_model=list[MobilizerRead])
async def list_mobilizers(
    session: SessionDep, user: CurrentUser, campaign: uuid.UUID | None = None
) -> list[Mobilizer]:
    statement = select(Mobilizer).options(*LOADED)
    if campaign is not None:
        statement = statement.where(Mobilizer.campaign_id == campaign)
    statement = limit_to_campaigns(
        statement, Mobilizer.campaign_id, await visible_campaign_ids(session, user)
    )
    own_ward = mobilizer_ward_id(user)
    if own_ward is not None:
        statement = statement.where(Mobilizer.ward_id == own_ward)
    statement = statement.join(Ward, Mobilizer.ward_id == Ward.id).order_by(
        Ward.name, Mobilizer.full_name
    )
    return list((await session.execute(statement)).scalars().all())


@router.post("/", response_model=MobilizerRead, status_code=status.HTTP_201_CREATED)
async def create_mobilizer(
    payload: MobilizerCreate,
    session: SessionDep,
    user: CurrentUser,
    _: Writer,
) -> Mobilizer:
    await require_visible_campaign(session, user, payload.campaign)

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
    return await _reload(session, mobilizer.id)


@router.delete("/{mobilizer_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mobilizer(
    mobilizer_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    _: Writer,
) -> Response:
    mobilizer = (
        await session.execute(select(Mobilizer).where(Mobilizer.id == mobilizer_id))
    ).scalar_one_or_none()
    if mobilizer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such mobilizer.")
    await require_visible_campaign(session, user, mobilizer.campaign_id)
    require_own_ward(user, mobilizer.ward_id)
    await session.delete(mobilizer)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _reload(session: SessionDep, mobilizer_id: uuid.UUID) -> Mobilizer:
    return (
        await session.execute(
            select(Mobilizer).where(Mobilizer.id == mobilizer_id).options(*LOADED)
        )
    ).scalar_one()
