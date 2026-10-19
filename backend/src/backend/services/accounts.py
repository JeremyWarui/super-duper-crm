"""Logins, and the one campaign each belongs to."""

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Campaign, CampaignMember, Mobilizer, OperationalGrain, User, UserRole
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


async def unit_holder(
    session: AsyncSession,
    campaign_id: uuid.UUID,
    ward_id: uuid.UUID | None,
    centre_id: uuid.UUID | None = None,
) -> Mobilizer | None:
    """The mobilizer on this ward, or on this centre, of the campaign."""
    if ward_id is None:
        return None
    statement = select(Mobilizer).where(Mobilizer.campaign_id == campaign_id)
    if centre_id is not None:
        statement = statement.where(Mobilizer.registration_centre_id == centre_id)
    else:
        statement = statement.where(
            Mobilizer.ward_id == ward_id, Mobilizer.registration_centre_id.is_(None)
        )
    return await session.scalar(statement)


def require_unit(
    campaign: Campaign, ward_id: uuid.UUID | None, centre_id: uuid.UUID | None
) -> None:
    """A whole ward in a seat organised by ward; a centre is allowed only in a ward race."""
    if centre_id is not None and ward_id is None:
        raise Refused("A registration centre needs its ward.")
    if centre_id is not None and campaign.operational_grain is not OperationalGrain.CENTRE:
        raise Refused("In this race a mobilizer works a whole ward; leave the centre out.")


async def move_mobilizer(
    session: AsyncSession,
    campaign: Campaign,
    mobilizer: Mobilizer,
    ward_id: uuid.UUID | None,
    centre_id: uuid.UUID | None = None,
) -> None:
    """Put a mobilizer on a unit, or on none; whoever held that unit is left unassigned."""
    require_unit(campaign, ward_id, centre_id)
    holder = await unit_holder(session, mobilizer.campaign_id, ward_id, centre_id)
    moved = [mobilizer]
    if holder is not None and holder.id != mobilizer.id:
        holder.ward_id = None
        holder.registration_centre_id = None
        await session.flush()
        moved.append(holder)
    mobilizer.ward_id = ward_id
    mobilizer.registration_centre_id = centre_id
    await session.flush()
    for row in moved:
        await session.refresh(row, ["ward", "registration_centre"])


async def add_mobilizer(
    session: AsyncSession,
    campaign: Campaign,
    ward_id: uuid.UUID | None,
    user: User | None = None,
    *,
    centre_id: uuid.UUID | None = None,
    full_name: str = "",
    phone: str = "",
) -> Mobilizer:
    """Put somebody on the campaign, on a free ward or none; a login given joins it too.

    Name and phone default to the login's.
    """
    require_unit(campaign, ward_id, centre_id)
    holder = await unit_holder(session, campaign.id, ward_id, centre_id)
    if holder is not None:
        unit = "centre" if centre_id is not None else "ward"
        raise Refused(f"That {unit} already has a mobilizer: {holder.full_name}.")
    if user is not None:
        await add_member(session, campaign.id, user)
        full_name = full_name or user.full_name or user.username
        phone = phone or user.phone
    mobilizer = Mobilizer(
        campaign_id=campaign.id,
        ward_id=ward_id,
        registration_centre_id=centre_id,
        user_id=user.id if user is not None else None,
        full_name=full_name,
        phone=phone,
    )
    session.add(mobilizer)
    await session.flush()
    return mobilizer
