"""Whether a campaign workspace is open.

A campaign is open until it is closed after the election; then it stays readable by its team,
refuses every change, and takes no more sign-ups.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Campaign, CampaignMember


@dataclass(frozen=True)
class Access:
    open: bool
    reason: str = ""
    read_only: bool = False


FULL = Access(open=True)
ENDED = Access(open=False, reason="This campaign has closed.")
READ_ONLY = Access(open=True, read_only=True, reason="This campaign is closed: it is read-only.")


async def workspace_access(session: AsyncSession, campaign_id: uuid.UUID) -> Access:
    """The access of one campaign to the public: a closed campaign takes no sign-ups. FULL for
    an unknown id, which the caller 404s."""
    closed = await session.scalar(select(Campaign.closed_at).where(Campaign.id == campaign_id))
    return ENDED if closed is not None else FULL


async def login_access(session: AsyncSession, user_id: uuid.UUID) -> Access:
    """The access of the campaign this login belongs to; FULL for a login with none."""
    closed = await session.scalar(
        select(Campaign.closed_at)
        .join(CampaignMember, CampaignMember.campaign_id == Campaign.id)
        .where(CampaignMember.user_id == user_id)
    )
    return READ_ONLY if closed is not None else FULL
