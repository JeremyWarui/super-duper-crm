"""The supporter register. Signing up is open; reading it is not."""

import uuid

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from backend.api.deps import (
    NOT_AUTHENTICATED,
    CurrentUser,
    OptionalUser,
    SessionDep,
    mobilizer_ward_id,
)
from backend.api.scope import (
    limit_to_campaigns,
    mobilizer_profile_for,
    require_own_ward,
    require_visible_campaign,
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
    payload: SupporterCreate, session: SessionDep, user: OptionalUser
) -> Supporter:
    """Sign someone up. Open, so a signed-out field form works."""
    mobilizer_id = payload.mobilizer
    if user is not None:
        await require_visible_campaign(session, user, payload.campaign)
        if payload.ward is not None:
            require_own_ward(user, payload.ward)
        profile = await mobilizer_profile_for(session, user)
        if profile is not None:
            mobilizer_id = payload.mobilizer or profile.id

    supporter = Supporter(
        campaign_id=payload.campaign,
        ward_id=payload.ward,
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
    supporter_id: uuid.UUID, session: SessionDep, user: OptionalUser
) -> Response:
    """Erase someone's details. The team only."""
    if user is None:
        raise NOT_AUTHENTICATED
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
