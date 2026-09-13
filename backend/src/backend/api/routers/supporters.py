"""The supporter register, for the campaign the caller is on."""

import uuid

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from backend.api.deps import (
    CurrentUser,
    SessionDep,
    mobilizer_ward_id,
)
from backend.api.scope import (
    limit_to_campaigns,
    mobilizer_profile_for,
    require_campaign_mobilizer,
    require_own_ward,
    require_visible_campaign,
    require_ward_in_campaign,
    visible_campaign_ids,
)
from backend.models import Supporter, User, UserRole
from backend.schemas.campaign import SupporterCreate, SupporterRead

router = APIRouter(prefix="/supporters", tags=["supporters"])

READERS = {UserRole.MANAGER, UserRole.MOBILIZER}


@router.get("/", response_model=list[SupporterRead])
async def list_supporters(
    session: SessionDep, user: CurrentUser, campaign: uuid.UUID | None = None
) -> list[Supporter]:
    if user.role not in READERS:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "The supporter register is for the campaign team."
        )
    statement = select(Supporter)
    if campaign is not None:
        statement = statement.where(Supporter.campaign_id == campaign)
    statement = limit_to_campaigns(
        statement, Supporter.campaign_id, await visible_campaign_ids(session, user)
    )
    own_ward = mobilizer_ward_id(user)
    if own_ward is not None:
        statement = statement.where(Supporter.ward_id == own_ward)
    statement = statement.order_by(Supporter.created_at.desc())
    return list((await session.execute(statement)).scalars().all())


@router.post("/", response_model=SupporterRead, status_code=status.HTTP_201_CREATED)
async def register_supporter(
    payload: SupporterCreate, session: SessionDep, user: CurrentUser
) -> Supporter:
    """Sign someone up, into the caller's own campaign.

    The campaign is named in the body, so without a signed-in caller to check it
    against, anyone holding a campaign's id could write into its register.
    """
    campaign = await require_visible_campaign(session, user, payload.campaign)
    await require_campaign_mobilizer(session, payload.campaign, payload.mobilizer)

    profile = await mobilizer_profile_for(session, user)
    mobilizer_id = payload.mobilizer
    ward_id = payload.ward
    if profile is not None and profile.campaign_id == payload.campaign:
        mobilizer_id = payload.mobilizer or profile.id
        # A mobilizer reads only their own ward, so what they register lands in it.
        ward_id = payload.ward or profile.ward_id
    if ward_id is not None:
        require_own_ward(user, ward_id)
        await require_ward_in_campaign(session, campaign, ward_id)

    supporter = Supporter(
        campaign_id=payload.campaign,
        ward_id=ward_id,
        mobilizer_id=mobilizer_id,
        full_name=payload.full_name,
        phone=payload.phone,
        support_level=payload.support_level,
        consent_given=payload.consent_given,
    )
    session.add(supporter)
    await session.commit()
    return supporter


@router.delete("/{supporter_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supporter(
    supporter_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> Response:
    """Erase someone's details. The team only."""
    if user.role not in READERS:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "The supporter register is for the campaign team."
        )
    supporter = await _visible_supporter(session, user, supporter_id)
    await session.delete(supporter)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _visible_supporter(session: SessionDep, user: User, supporter_id: uuid.UUID) -> Supporter:
    supporter = await session.get(Supporter, supporter_id)
    if supporter is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such supporter.")
    await require_visible_campaign(session, user, supporter.campaign_id)
    if supporter.ward_id is not None:
        require_own_ward(user, supporter.ward_id)
    return supporter
