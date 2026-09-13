"""Who may be put on a campaign."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import CampaignMember, User, UserRole, member_refusal


async def membership_refusal(
    session: AsyncSession, named: User, campaign_id: uuid.UUID
) -> str | None:
    """Why this login may not join this campaign, or None if it may.

    A campaign is for one candidate, so a candidate cannot join one that already
    has its candidate. A mobilizer works one ward on one campaign:
    `Mobilizer.user_id` is unique, and everything a mobilizer reads and writes is
    scoped by that one row.
    """
    refusal = member_refusal(named)
    if refusal is not None:
        return refusal
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
    if named.role is UserRole.MOBILIZER:
        elsewhere = await session.scalar(
            select(CampaignMember.campaign_id).where(
                CampaignMember.user_id == named.id, CampaignMember.campaign_id != campaign_id
            )
        )
        if elsewhere is not None:
            return (
                f"{named.username} already works a ward on another campaign; a mobilizer works one."
            )
    return None
