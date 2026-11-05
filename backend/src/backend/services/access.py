"""Whether a campaign workspace is open.

Party and standalone workspaces are always open. A hosted workspace is open while its aspirant
is approved, and always when it has none.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Aspirant, AspirantStatus, Campaign, CampaignMember, WorkspaceKind


@dataclass(frozen=True)
class Access:
    open: bool
    reason: str = ""


FULL = Access(open=True)
SUSPENDED = Access(open=False, reason="This campaign is suspended by the party.")
CLOSED = Access(open=False, reason="This campaign is closed: its aspirant has withdrawn.")


def rule(kind: WorkspaceKind, aspirant: AspirantStatus | None) -> Access:
    """The access a workspace of this kind has, given its aspirant's status."""
    if kind is not WorkspaceKind.HOSTED or aspirant in (None, AspirantStatus.APPROVED):
        return FULL
    return SUSPENDED if aspirant is AspirantStatus.SUSPENDED else CLOSED


def _kind_and_aspirant() -> Select:
    return select(Campaign.kind, Aspirant.status).outerjoin(
        Aspirant, Aspirant.campaign_id == Campaign.id
    )


async def workspace_access(session: AsyncSession, campaign_id: uuid.UUID) -> Access:
    """The access of one campaign; FULL for an unknown id, which the caller 404s."""
    row = (await session.execute(_kind_and_aspirant().where(Campaign.id == campaign_id))).first()
    return rule(*row) if row else FULL


async def login_access(session: AsyncSession, user_id: uuid.UUID) -> Access:
    """The access of the campaign this login belongs to; FULL for a login with none."""
    row = (
        await session.execute(
            _kind_and_aspirant()
            .join(CampaignMember, CampaignMember.campaign_id == Campaign.id)
            .where(CampaignMember.user_id == user_id)
        )
    ).first()
    return rule(*row) if row else FULL
