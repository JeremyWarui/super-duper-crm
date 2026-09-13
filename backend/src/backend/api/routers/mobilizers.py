"""Ground organizers: who is working which ward."""

import uuid

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from backend.api.deps import CurrentUser, SessionDep, Writer, mobilizer_ward_id
from backend.api.scope import (
    add_member,
    limit_to_campaigns,
    require_own_ward,
    require_visible_campaign,
    require_ward_in_campaign,
    visible_campaign_ids,
)
from backend.models import CampaignMember, Mobilizer, User, UserRole, Ward
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
    campaign = await require_visible_campaign(session, user, payload.campaign)
    await require_ward_in_campaign(session, campaign, payload.ward, payload.registration_centre)
    if payload.user is not None:
        await _check_login(session, payload.campaign, payload.user)
        # Reads are scoped by membership, so a login attached here and nowhere
        # else would sign in to an empty app.
        await add_member(session, payload.campaign, payload.user)

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


async def _check_login(session: SessionDep, campaign_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """The login being put on the ground must be free to take it.

    A mobilizer works under the ward held on their own campaign, so one already
    belonging to another campaign cannot be planted here. A login that already
    has a ground row anywhere is refused too, which is also what keeps the
    uniqueness rule on `Mobilizer.user_id` from surfacing as a 500.
    """
    named = await session.get(User, user_id)
    if named is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No such user.")
    if named.role is not UserRole.MOBILIZER:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{named.username} is not a mobilizer.")

    elsewhere = await visible_campaign_ids(session, named)
    if elsewhere - {campaign_id}:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"{named.username} is on another campaign."
        )

    taken = await session.scalar(select(Mobilizer.id).where(Mobilizer.user_id == user_id))
    if taken is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"{named.username} is already on the ground somewhere."
        )


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
    if mobilizer.user_id is not None:
        # Their ward went with the row, so a mobilizer's membership would sign
        # them in to a campaign they can read nothing of. Only a mobilizer's:
        # a candidate or a manager may also hold a ground row, and the campaign
        # is not this route's to take off them.
        await session.execute(
            delete(CampaignMember).where(
                CampaignMember.campaign_id == mobilizer.campaign_id,
                CampaignMember.user_id == mobilizer.user_id,
                CampaignMember.role == UserRole.MOBILIZER,
            )
        )
    await session.delete(mobilizer)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _reload(session: SessionDep, mobilizer_id: uuid.UUID) -> Mobilizer:
    return (
        await session.execute(
            select(Mobilizer).where(Mobilizer.id == mobilizer_id).options(*LOADED)
        )
    ).scalar_one()
