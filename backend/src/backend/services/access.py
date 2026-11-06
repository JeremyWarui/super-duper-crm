"""Whether a campaign workspace is open.

Party and standalone workspaces are open. A hosted workspace is open while its aspirant is
approved, and always when it has none. A campaign closed after the election stays readable by its
team, refuses every change, and takes no more sign-ups.
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
    read_only: bool = False


FULL = Access(open=True)
SUSPENDED = Access(open=False, reason="This campaign is suspended by the party.")
CLOSED = Access(open=False, reason="This campaign is closed: its aspirant has withdrawn.")
ENDED = Access(open=False, reason="This campaign has closed.")
READ_ONLY = Access(open=True, read_only=True, reason="This campaign is closed: it is read-only.")


def rule(kind: WorkspaceKind, aspirant: AspirantStatus | None, closed: bool = False) -> Access:
    """The access a workspace of this kind has to its team, given its aspirant's status."""
    if kind is WorkspaceKind.HOSTED and aspirant not in (None, AspirantStatus.APPROVED):
        return SUSPENDED if aspirant is AspirantStatus.SUSPENDED else CLOSED
    return READ_ONLY if closed else FULL


def _kind_and_aspirant() -> Select:
    return select(Campaign.kind, Aspirant.status, Campaign.closed_at.is_not(None)).outerjoin(
        Aspirant, Aspirant.campaign_id == Campaign.id
    )


async def workspace_access(session: AsyncSession, campaign_id: uuid.UUID) -> Access:
    """The access of one campaign to the public: a read-only campaign takes no sign-ups. FULL for
    an unknown id, which the caller 404s."""
    row = (await session.execute(_kind_and_aspirant().where(Campaign.id == campaign_id))).first()
    found = rule(*row) if row else FULL
    return ENDED if found.read_only else found


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
