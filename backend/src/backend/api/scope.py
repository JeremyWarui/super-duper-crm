"""Which campaigns a caller may see, and which rows inside them."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Campaign, Mobilizer, User, UserRole

NOTHING: frozenset[uuid.UUID] = frozenset()


async def visible_campaign_ids(session: AsyncSession, user: User) -> frozenset[uuid.UUID] | None:
    """The campaigns this caller may read. None means every campaign."""
    if user.role is UserRole.MANAGER:
        return None
    if user.role is UserRole.CANDIDATE:
        rows = await session.execute(select(Campaign.id).where(Campaign.candidate_id == user.id))
        return frozenset(rows.scalars())
    profile = user.mobilizer_profile
    if profile is None:
        return NOTHING
    return frozenset({profile.campaign_id})


def limit_to_campaigns(
    statement: Select, column, campaign_ids: frozenset[uuid.UUID] | None
) -> Select:
    if campaign_ids is None:
        return statement
    return statement.where(column.in_(campaign_ids))


async def require_visible_campaign(
    session: AsyncSession, user: User, campaign_id: uuid.UUID
) -> Campaign:
    """The campaign, or 404 when the caller has no business with it."""
    campaign = await session.get(Campaign, campaign_id)
    visible = await visible_campaign_ids(session, user)
    if campaign is None or (visible is not None and campaign.id not in visible):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such campaign.")
    return campaign


def require_own_ward(user: User, ward_id: uuid.UUID) -> None:
    """Stop a mobilizer writing into somebody else's ward."""
    if user.role is not UserRole.MOBILIZER:
        return
    profile = user.mobilizer_profile
    if profile is None or profile.ward_id != ward_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "A mobilizer may only work in their own ward."
        )


async def mobilizer_profile_for(session: AsyncSession, user: User) -> Mobilizer | None:
    """The caller's own mobilizer row."""
    if user.role is not UserRole.MOBILIZER:
        return None
    return user.mobilizer_profile
