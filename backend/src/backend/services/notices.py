"""Notices under the bell: who gets one when something waits for them, and the push that goes
with it."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import CampaignMember, Notice, UserRole
from backend.services import push, units

# The longest preview line a notice keeps.
DETAIL_MAX = 200

SIGNUPS_PAGE = "/campaign/signups"
PAYMENTS_PAGE = "/campaign/payments"
DECIDES_SIGNUPS = (UserRole.CANDIDATE, UserRole.MANAGER, UserRole.COORDINATOR)


def preview(text: str) -> str:
    """The first line of `text`, cut to DETAIL_MAX characters."""
    first = next((line.strip() for line in (text or "").splitlines() if line.strip()), "")
    return first if len(first) <= DETAIL_MAX else first[: DETAIL_MAX - 1].rstrip() + "…"


async def tell(
    session: AsyncSession,
    campaign_id: uuid.UUID,
    user_ids: list[uuid.UUID],
    text: str,
    url: str,
    *,
    detail: str = "",
    sender_id: uuid.UUID | None = None,
    title: str = "",
) -> int:
    """Give each login a notice and push it to their devices; returns how many devices took
    the push. Commits."""
    people = list(dict.fromkeys(u for u in user_ids if u != sender_id))
    session.add_all(
        Notice(
            campaign_id=campaign_id,
            user_id=user_id,
            text=text,
            url=url,
            detail=preview(detail),
            sender_id=sender_id,
        )
        for user_id in people
    )
    await session.commit()
    return await push.notify(session, people, title or text, preview(detail) or text, url)


async def _with_roles(
    session: AsyncSession, campaign_id: uuid.UUID, user_ids: list[uuid.UUID], roles
) -> list[uuid.UUID]:
    return list(
        await session.scalars(
            select(CampaignMember.user_id).where(
                CampaignMember.campaign_id == campaign_id,
                CampaignMember.user_id.in_(user_ids),
                CampaignMember.role.in_(roles),
            )
        )
    )


async def signup_waiting(
    session: AsyncSession,
    campaign_id: uuid.UUID,
    ward_id: uuid.UUID | None,
    centre_id: uuid.UUID | None,
    name: str,
    role_label: str,
) -> int:
    """Tell the candidate, the manager and the coordinators over this place that a team
    sign-up waits for a decision."""
    found = await units.logins(session, campaign_id, ward_id, centre_id)
    deciders = await _with_roles(session, campaign_id, found, DECIDES_SIGNUPS)
    return await tell(
        session,
        campaign_id,
        deciders,
        f"Team sign-up waiting: {name}",
        SIGNUPS_PAGE,
        detail=f"Wants to join as {role_label.lower()}.",
        title="Team sign-up waiting",
    )


async def payment_waiting(
    session: AsyncSession,
    campaign_id: uuid.UUID,
    approver: UserRole,
    scheduler_id: uuid.UUID,
    recipient: str,
    amount_kes: int,
    work: str,
) -> int:
    """Tell everyone who may approve this payment, but whoever scheduled it, that it waits."""
    approvers = list(
        await session.scalars(
            select(CampaignMember.user_id).where(
                CampaignMember.campaign_id == campaign_id, CampaignMember.role == approver
            )
        )
    )
    return await tell(
        session,
        campaign_id,
        approvers,
        f"Payment to approve: KES {amount_kes:,} to {recipient}",
        PAYMENTS_PAGE,
        detail=work,
        sender_id=scheduler_id,
        title="Payment to approve",
    )
