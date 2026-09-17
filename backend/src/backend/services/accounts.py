"""Logins, and the one campaign each belongs to."""

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Campaign, CampaignMember, Mobilizer, User, UserRole, Ward
from backend.security import hash_password, new_password
from backend.services.errors import Refused


async def user_named(session: AsyncSession, username: str) -> User | None:
    return await session.scalar(select(User).where(User.username == username))


async def new_login(
    session: AsyncSession,
    *,
    username: str,
    role: UserRole,
    password: str | None = None,
    first_name: str = "",
    last_name: str = "",
    email: str = "",
    phone: str = "",
    is_superuser: bool = False,
) -> tuple[User, str]:
    """Create a login and return it with its password, generated when none is given."""
    taken = f"The username {username} is already taken."
    if await user_named(session, username) is not None:
        raise Refused(taken)
    chosen = password or new_password()
    user = User(
        username=username,
        role=role,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        is_superuser=is_superuser,
        password_hash=hash_password(chosen),
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as clash:
        await session.rollback()
        raise Refused(taken) from clash
    return user, chosen


async def campaign_of(session: AsyncSession, user_id: uuid.UUID) -> Campaign | None:
    """The campaign this login is on, or None."""
    return await session.scalar(
        select(Campaign)
        .join(CampaignMember, CampaignMember.campaign_id == Campaign.id)
        .where(CampaignMember.user_id == user_id)
    )


async def membership_refusal(
    session: AsyncSession, user: User, campaign_id: uuid.UUID
) -> str | None:
    """Why this login may not join this campaign, or None if it may."""
    if user.is_superuser:
        return (
            "A superuser reaches every campaign through the console, and would lose the "
            "campaign app by being put on one."
        )
    if not user.is_active:
        return f"{user.username} is disabled, so they could not sign in to work on it."
    current = await campaign_of(session, user.id)
    if current is not None and current.id != campaign_id:
        return f"{user.username} is already on {current.title}; a login belongs to one campaign."
    if user.role is UserRole.CANDIDATE:
        sitting = await session.scalar(
            select(CampaignMember.user_id).where(
                CampaignMember.campaign_id == campaign_id,
                CampaignMember.role == UserRole.CANDIDATE,
                CampaignMember.user_id != user.id,
            )
        )
        if sitting is not None:
            return f"{user.username} is a candidate, and that campaign already has its candidate."
    return None


async def add_member(session: AsyncSession, campaign_id: uuid.UUID, user: User) -> CampaignMember:
    """Put a login on a campaign, in the place its role names."""
    existing = await session.scalar(
        select(CampaignMember).where(
            CampaignMember.campaign_id == campaign_id, CampaignMember.user_id == user.id
        )
    )
    if existing is not None:
        return existing
    refusal = await membership_refusal(session, user, campaign_id)
    if refusal is not None:
        raise Refused(refusal)
    member = CampaignMember(campaign_id=campaign_id, user_id=user.id, role=user.role)
    session.add(member)
    await session.flush()
    return member


async def add_mobilizer(
    session: AsyncSession,
    campaign: Campaign,
    ward: Ward,
    user: User,
    centre_id: uuid.UUID | None = None,
) -> Mobilizer:
    """Put a mobilizer's login on a campaign and on one of its wards."""
    await add_member(session, campaign.id, user)
    mobilizer = Mobilizer(
        campaign_id=campaign.id,
        ward_id=ward.id,
        registration_centre_id=centre_id,
        user_id=user.id,
        full_name=user.full_name or user.username,
        phone=user.phone,
    )
    session.add(mobilizer)
    await session.flush()
    return mobilizer
