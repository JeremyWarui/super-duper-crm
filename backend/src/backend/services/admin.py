"""Operations across every campaign, for a superuser through the console or the command line."""

import uuid

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    AuthToken,
    Campaign,
    CampaignMember,
    Event,
    Mobilizer,
    Supporter,
    Target,
    User,
    UserRole,
    Ward,
)
from backend.schemas.admin import (
    AdminCampaignRead,
    AdminUserRead,
    AdminWardRead,
    MemberRead,
    Totals,
)
from backend.security import hash_password, new_password
from backend.services.accounts import add_member as join
from backend.services.accounts import add_mobilizer, new_login, user_named
from backend.services.errors import NotFound, Refused
from backend.services.targets import ward_in_area, wards_in_area

SIZED = {"targets": Target, "mobilizers": Mobilizer, "events": Event, "supporters": Supporter}


async def totals(session: AsyncSession) -> Totals:
    """One row count per table."""
    tables = {"campaigns": Campaign, "users": User, "members": CampaignMember, **SIZED}
    return Totals(
        **{
            name: await session.scalar(select(func.count()).select_from(model))
            for name, model in tables.items()
        }
    )


async def _campaign(session: AsyncSession, campaign_id: uuid.UUID) -> Campaign:
    found = await session.get(Campaign, campaign_id)
    if found is None:
        raise NotFound("No such campaign.")
    return found


async def _user(session: AsyncSession, user_id: uuid.UUID) -> User:
    found = await session.get(User, user_id)
    if found is None:
        raise NotFound("No such user.")
    return found


async def campaigns(
    session: AsyncSession, campaign_id: uuid.UUID | None = None
) -> list[AdminCampaignRead]:
    """Every campaign, or one, with its team, wards and size, oldest first."""
    statement = (
        select(Campaign)
        .options(selectinload(Campaign.members).selectinload(CampaignMember.user))
        .order_by(Campaign.created_at)
    )
    if campaign_id is not None:
        statement = statement.where(Campaign.id == campaign_id)
    found = list((await session.scalars(statement)).all())
    ids = [c.id for c in found]

    counts = {}
    for name, model in SIZED.items():
        rows = await session.execute(
            select(model.campaign_id, func.count())
            .where(model.campaign_id.in_(ids))
            .group_by(model.campaign_id)
        )
        counts[name] = dict(rows.tuples().all())
    votes = {
        row[0]: (row[1] or 0, row[2] or 0)
        for row in await session.execute(
            select(
                Target.campaign_id, func.sum(Target.votes_needed), func.sum(Target.votes_committed)
            )
            .where(Target.campaign_id.in_(ids))
            .group_by(Target.campaign_id)
        )
    }

    rows = []
    for campaign in found:
        members = sorted(campaign.members, key=lambda m: (m.role.value, m.user.username))
        needed, committed = votes.get(campaign.id, (0, 0))
        rows.append(
            AdminCampaignRead(
                id=campaign.id,
                title=campaign.title,
                office_level=campaign.office_level.value,
                candidate=next(
                    (m.user.username for m in members if m.role is UserRole.CANDIDATE), ""
                ),
                election_date=campaign.election_date.isoformat()
                if campaign.election_date
                else None,
                members=[
                    MemberRead(
                        user_id=m.user_id,
                        username=m.user.username,
                        full_name=m.user.full_name,
                        role=m.role,
                    )
                    for m in members
                ],
                wards=[
                    AdminWardRead(id=w.id, name=w.name)
                    for w in await wards_in_area(session, campaign)
                ],
                **{name: counted.get(campaign.id, 0) for name, counted in counts.items()},
                votes_needed=int(needed),
                votes_committed=int(committed),
            )
        )
    return rows


async def campaign(session: AsyncSession, campaign_id: uuid.UUID) -> AdminCampaignRead:
    found = await campaigns(session, campaign_id)
    if not found:
        raise NotFound("No such campaign.")
    return found[0]


async def users(
    session: AsyncSession,
    role: UserRole | None = None,
    campaign_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> list[AdminUserRead]:
    """Every login matching the filters, with the title of the campaign it is on."""
    statement = (
        select(User, Campaign.title)
        .outerjoin(CampaignMember, CampaignMember.user_id == User.id)
        .outerjoin(Campaign, Campaign.id == CampaignMember.campaign_id)
        .order_by(User.username)
    )
    if role is not None:
        statement = statement.where(User.role == role)
    if campaign_id is not None:
        statement = statement.where(CampaignMember.campaign_id == campaign_id)
    if user_id is not None:
        statement = statement.where(User.id == user_id)
    return [
        AdminUserRead(
            id=login.id,
            username=login.username,
            full_name=login.full_name,
            email=login.email,
            phone=login.phone,
            role=login.role,
            is_active=login.is_active,
            is_superuser=login.is_superuser,
            last_login_at=login.last_login_at.isoformat() if login.last_login_at else None,
            campaign=title,
        )
        for login, title in await session.execute(statement)
    ]


async def user(session: AsyncSession, user_id: uuid.UUID) -> AdminUserRead:
    found = await users(session, user_id=user_id)
    if not found:
        raise NotFound("No such user.")
    return found[0]


async def user_by_name(session: AsyncSession, username: str) -> User:
    found = await user_named(session, username)
    if found is None:
        raise NotFound(f"No user called {username}.")
    return found


async def reset_password(session: AsyncSession, user_id: uuid.UUID, password: str | None) -> str:
    """Give a login a new password and sign out its session."""
    login = await _user(session, user_id)
    if not login.is_active:
        raise Refused(
            f"{login.username} is disabled, so a new password would not sign them in. "
            "Enable the login first."
        )
    chosen = password or new_password()
    login.password_hash = hash_password(chosen)
    await session.execute(delete(AuthToken).where(AuthToken.user_id == login.id))
    await session.commit()
    return chosen


async def set_active(session: AsyncSession, user_id: uuid.UUID, active: bool) -> User:
    """Turn a login on or off; off signs it out. The last active superuser stays on."""
    login = await _user(session, user_id)
    if login.is_superuser and not active:
        others = await session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.is_superuser.is_(True), User.is_active.is_(True), User.id != login.id)
        )
        if not others:
            raise Refused("That is the only superuser left, so nothing could run the console.")
    login.is_active = active
    if not active:
        await session.execute(delete(AuthToken).where(AuthToken.user_id == login.id))
    await session.commit()
    return login


async def add_member(
    session: AsyncSession, campaign_id: uuid.UUID, user_id: uuid.UUID
) -> CampaignMember:
    target = await _campaign(session, campaign_id)
    login = await session.get(User, user_id)
    if login is None:
        raise Refused("No such user.")
    member = await join(session, target.id, login)
    await session.commit()
    return member


async def remove_member(session: AsyncSession, campaign_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Take somebody off a campaign, freeing a mobilizer's ground row there; the login stays."""
    await _campaign(session, campaign_id)
    place = await session.scalar(
        select(CampaignMember.role).where(
            CampaignMember.campaign_id == campaign_id, CampaignMember.user_id == user_id
        )
    )
    if place is None:
        raise Refused("They are not on that campaign.")
    if place is UserRole.CANDIDATE:
        raise Refused("That is the candidate this campaign is for; delete the campaign instead.")
    await session.execute(
        delete(CampaignMember).where(
            CampaignMember.campaign_id == campaign_id, CampaignMember.user_id == user_id
        )
    )
    await session.execute(
        update(Mobilizer)
        .where(Mobilizer.campaign_id == campaign_id, Mobilizer.user_id == user_id)
        .values(user_id=None)
    )
    await session.commit()


async def rename_campaign(session: AsyncSession, campaign_id: uuid.UUID, title: str) -> Campaign:
    renamed = await _campaign(session, campaign_id)
    if not title.strip():
        raise Refused("A campaign needs a name.")
    renamed.title = title.strip()
    await session.commit()
    return renamed


async def logins_on(session: AsyncSession, campaign_id: uuid.UUID) -> list[User]:
    """The logins on a campaign, by username."""
    statement = (
        select(User)
        .join(CampaignMember, CampaignMember.user_id == User.id)
        .where(CampaignMember.campaign_id == campaign_id)
        .order_by(User.username)
    )
    return list((await session.scalars(statement)).all())


async def remove_campaign(session: AsyncSession, campaign_id: uuid.UUID) -> list[str]:
    """Delete a campaign, everything on it and its people's logins, without committing.

    Returns the deleted usernames.
    """
    people = await logins_on(session, campaign_id)
    if people:
        await session.execute(delete(User).where(User.id.in_([p.id for p in people])))
    # The database's ON DELETE rules take the rest.
    await session.execute(delete(Campaign).where(Campaign.id == campaign_id))
    return [p.username for p in people]


async def delete_campaign(session: AsyncSession, campaign_id: uuid.UUID) -> list[str]:
    """Delete a campaign, everything on it and its people's logins; returns their usernames."""
    await _campaign(session, campaign_id)
    gone = await remove_campaign(session, campaign_id)
    await session.commit()
    return gone


async def create_user(
    session: AsyncSession,
    *,
    username: str,
    role: UserRole,
    first_name: str = "",
    last_name: str = "",
    email: str = "",
    phone: str = "",
    campaign_id: uuid.UUID | None = None,
    ward_id: uuid.UUID | None = None,
) -> tuple[User, str]:
    """Create a login, on a campaign when one is named; returns it and its password."""
    target = await session.get(Campaign, campaign_id) if campaign_id is not None else None
    if campaign_id is not None and target is None:
        raise Refused("No such campaign.")
    ward: Ward | None = None
    if role is UserRole.MOBILIZER:
        if target is None:
            raise Refused("A mobilizer needs a campaign and a ward, or they sign in to nothing.")
        if ward_id is None:
            raise Refused("A mobilizer needs a ward, or they sign in to nothing.")
        ward = await session.get(Ward, ward_id)
        if ward is None:
            raise Refused("No such ward.")
        if not await ward_in_area(session, target, ward_id):
            raise Refused(f"{ward.name} is not a ward {target.title} works.")
    if role is UserRole.CANDIDATE and target is not None:
        sitting = await session.scalar(
            select(User.username)
            .join(CampaignMember, CampaignMember.user_id == User.id)
            .where(
                CampaignMember.campaign_id == target.id, CampaignMember.role == UserRole.CANDIDATE
            )
        )
        taken = f"is already {sitting}'s campaign" if sitting else "has no candidate"
        raise Refused(
            f"{target.title} {taken}. "
            "Create the aspirant on their own, then put them on a campaign."
        )

    created, password = await new_login(
        session,
        username=username,
        role=role,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
    )
    if ward is not None:
        await add_mobilizer(session, target, ward.id, created)
    elif target is not None:
        await join(session, target.id, created)
    await session.commit()
    return created, password
