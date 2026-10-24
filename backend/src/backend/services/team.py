"""A campaign's own people: who is on it, its one manager, and new passwords."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AuthToken, Campaign, CampaignMember, User, UserRole
from backend.services.accounts import add_member, new_login
from backend.services.errors import Forbidden, NotFound, Refused

ORDER = {UserRole.CANDIDATE: 0, UserRole.MANAGER: 1, UserRole.MOBILIZER: 2}


async def team(session: AsyncSession, campaign_id: uuid.UUID) -> list[User]:
    """The logins on a campaign: aspirant, manager, then mobilizers by username."""
    found = await session.scalars(
        select(User)
        .join(CampaignMember, CampaignMember.user_id == User.id)
        .where(CampaignMember.campaign_id == campaign_id)
    )
    return sorted(found, key=lambda u: (ORDER.get(u.role, 3), u.username))


async def manager_of(session: AsyncSession, campaign_id: uuid.UUID) -> User | None:
    return await session.scalar(
        select(User)
        .join(CampaignMember, CampaignMember.user_id == User.id)
        .where(CampaignMember.campaign_id == campaign_id, CampaignMember.role == UserRole.MANAGER)
    )


async def set_manager(
    session: AsyncSession, campaign: Campaign, details: dict, *, replace: bool
) -> tuple[User, str, str | None]:
    """Give a campaign a new manager login, shown with its password once.

    With `replace` the sitting manager is taken off the campaign, turned off and signed out.
    Returns the new login, its password and the replaced manager's username.
    """
    sitting = await manager_of(session, campaign.id)
    replaced = sitting.username if sitting is not None else None
    if sitting is not None and not replace:
        raise Refused(f"{campaign.title} already has a manager, {replaced}. Replace them instead.")
    try:
        created, password = await new_login(session, role=UserRole.MANAGER, **details)
        if sitting is not None:
            await session.execute(
                delete(CampaignMember).where(
                    CampaignMember.campaign_id == campaign.id, CampaignMember.user_id == sitting.id
                )
            )
            await session.execute(delete(AuthToken).where(AuthToken.user_id == sitting.id))
            sitting.is_active = False
        await add_member(session, campaign.id, created)
    except Refused:
        await session.rollback()
        raise
    await session.commit()
    return created, password, replaced


async def resettable(
    session: AsyncSession, caller: User, campaign_id: uuid.UUID, user_id: uuid.UUID
) -> User:
    """The teammate whose password the caller may reset; refused otherwise.

    The aspirant resets the manager and the mobilizers; the manager resets the mobilizers.
    """
    member = await session.scalar(
        select(User)
        .join(CampaignMember, CampaignMember.user_id == User.id)
        .where(CampaignMember.campaign_id == campaign_id, User.id == user_id)
    )
    if member is None:
        raise NotFound("No such person on this campaign.")
    if member.role is UserRole.CANDIDATE:
        raise Forbidden("Only an admin resets the aspirant's password.")
    if member.role is UserRole.MANAGER and caller.role is not UserRole.CANDIDATE:
        raise Forbidden("Only the aspirant resets the manager's password.")
    return member
