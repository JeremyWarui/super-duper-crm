"""Who may be put on a campaign."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Campaign, CampaignMember, Mobilizer, User, UserRole, member_refusal


async def campaign_of(session: AsyncSession, user_id: uuid.UUID) -> Campaign | None:
    """The one campaign this login is on, by membership or by a ground row, or None."""
    member_of = await session.scalar(
        select(Campaign)
        .join(CampaignMember, CampaignMember.campaign_id == Campaign.id)
        .where(CampaignMember.user_id == user_id)
    )
    if member_of is not None:
        return member_of
    return await session.scalar(
        select(Campaign)
        .join(Mobilizer, Mobilizer.campaign_id == Campaign.id)
        .where(Mobilizer.user_id == user_id)
    )


async def membership_refusal(
    session: AsyncSession, named: User, campaign_id: uuid.UUID
) -> str | None:
    """Why this login may not join this campaign, or None if it may.

    A login belongs to one campaign, and a campaign is for one candidate.
    """
    refusal = member_refusal(named)
    if refusal is not None:
        return refusal
    current = await campaign_of(session, named.id)
    if current is not None and current.id != campaign_id:
        return f"{named.username} is already on {current.title}; a login belongs to one campaign."
    if named.role is UserRole.CANDIDATE:
        sitting = await session.scalar(
            select(CampaignMember.user_id).where(
                CampaignMember.campaign_id == campaign_id,
                CampaignMember.role == UserRole.CANDIDATE,
                CampaignMember.user_id != named.id,
            )
        )
        if sitting is not None:
            return f"{named.username} is a candidate, and that campaign already has its candidate."
    return None
