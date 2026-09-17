"""Cross-campaign operations, for whoever runs the deployment.

Everything here reads past the membership scoping that holds every other route,
so it is the one place in the codebase that can. It is reached only by a
superuser, and only through `/api/admin/` or the command line; nothing in
`backend.api.scope` calls into it, and it calls nothing there.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
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
from backend.security import hash_password, new_password
from backend.services.membership import membership_refusal
from backend.services.targets import ward_in_area, wards_in_area


class AdminError(Exception):
    """Something the caller asked for cannot be done, with a reason to show them."""


class NotFound(AdminError):
    """The user or campaign a route names in its path does not exist."""


@dataclass
class MemberRow:
    user_id: uuid.UUID
    username: str
    full_name: str
    role: UserRole


@dataclass
class WardRow:
    id: uuid.UUID
    name: str


@dataclass
class CampaignRow:
    """One campaign, its team and how much of it exists."""

    id: uuid.UUID
    title: str
    office_level: str
    candidate: str
    election_date: str | None
    members: list[MemberRow]
    # The wards this campaign works, so a mobilizer can be given one of them.
    wards: list[WardRow]
    targets: int
    mobilizers: int
    events: int
    supporters: int
    votes_needed: int
    votes_committed: int


@dataclass
class UserRow:
    id: uuid.UUID
    username: str
    full_name: str
    email: str
    phone: str
    role: UserRole
    is_active: bool
    is_superuser: bool
    last_login_at: str | None
    campaigns: list[tuple[uuid.UUID, str, UserRole]]
    """campaign id, title, the place they hold on it."""


@dataclass
class Totals:
    campaigns: int
    users: int
    members: int
    targets: int
    mobilizers: int
    events: int
    supporters: int


async def totals(session: AsyncSession) -> Totals:
    """One number per table, for the top of the dashboard."""

    async def count(model: type) -> int:
        return (await session.execute(select(func.count()).select_from(model))).scalar_one()

    return Totals(
        campaigns=await count(Campaign),
        users=await count(User),
        members=await count(CampaignMember),
        targets=await count(Target),
        mobilizers=await count(Mobilizer),
        events=await count(Event),
        supporters=await count(Supporter),
    )


async def _counts_by_campaign(session: AsyncSession, model: type) -> dict[uuid.UUID, int]:
    rows = await session.execute(
        select(model.campaign_id, func.count()).group_by(model.campaign_id)
    )
    return {campaign_id: total for campaign_id, total in rows}


async def campaigns(
    session: AsyncSession, campaign_id: uuid.UUID | None = None
) -> list[CampaignRow]:
    """Every campaign, or one of them, with its team and its size."""
    statement = select(Campaign).options(
        selectinload(Campaign.candidate),
        selectinload(Campaign.members).selectinload(CampaignMember.user),
    )
    if campaign_id is not None:
        statement = statement.where(Campaign.id == campaign_id)
    found = list((await session.execute(statement)).scalars())

    targets = await _counts_by_campaign(session, Target)
    mobilizers = await _counts_by_campaign(session, Mobilizer)
    events = await _counts_by_campaign(session, Event)
    supporters = await _counts_by_campaign(session, Supporter)
    votes = {
        campaign: (needed or 0, committed or 0)
        for campaign, needed, committed in (
            await session.execute(
                select(
                    Target.campaign_id,
                    func.sum(Target.votes_needed),
                    func.sum(Target.votes_committed),
                ).group_by(Target.campaign_id)
            )
        )
    }

    rows = []
    for campaign in sorted(found, key=lambda c: c.created_at):
        needed, committed = votes.get(campaign.id, (0, 0))
        wards = [WardRow(id=w.id, name=w.name) for w in await wards_in_area(session, campaign)]
        rows.append(
            CampaignRow(
                id=campaign.id,
                title=campaign.title,
                office_level=campaign.office_level.value,
                candidate=campaign.candidate.username if campaign.candidate else "",
                election_date=(
                    campaign.election_date.isoformat() if campaign.election_date else None
                ),
                wards=wards,
                members=sorted(
                    (
                        MemberRow(
                            user_id=m.user_id,
                            username=m.user.username,
                            full_name=m.user.full_name,
                            role=m.role,
                        )
                        for m in campaign.members
                    ),
                    key=lambda m: (m.role.value, m.username),
                ),
                targets=targets.get(campaign.id, 0),
                mobilizers=mobilizers.get(campaign.id, 0),
                events=events.get(campaign.id, 0),
                supporters=supporters.get(campaign.id, 0),
                votes_needed=int(needed),
                votes_committed=int(committed),
            )
        )
    return rows


async def users(
    session: AsyncSession,
    role: UserRole | None = None,
    campaign_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> list[UserRow]:
    """Every login, or one of them, and the campaigns each one reaches."""
    statement = select(User).order_by(User.username).options(selectinload(User.memberships))
    if role is not None:
        statement = statement.where(User.role == role)
    if user_id is not None:
        statement = statement.where(User.id == user_id)
    found = list((await session.execute(statement)).scalars())

    titles = {row.id: row.title for row in (await session.execute(select(Campaign))).scalars()}

    rows = []
    for user in found:
        places = [
            (m.campaign_id, titles.get(m.campaign_id, str(m.campaign_id)), m.role)
            for m in user.memberships
        ]
        if campaign_id is not None and not any(c == campaign_id for c, _, _ in places):
            continue
        rows.append(
            UserRow(
                id=user.id,
                username=user.username,
                full_name=user.full_name,
                email=user.email,
                phone=user.phone,
                role=user.role,
                is_active=user.is_active,
                is_superuser=user.is_superuser,
                last_login_at=(
                    user.last_login_at.isoformat() if user.last_login_at is not None else None
                ),
                campaigns=sorted(places, key=lambda p: p[1]),
            )
        )
    return rows


async def reset_password(session: AsyncSession, user_id: uuid.UUID, password: str | None) -> str:
    """Give a login a new password and sign out every session it has."""
    user = await session.get(User, user_id)
    if user is None:
        raise NotFound("No such user.")
    if not user.is_active:
        raise AdminError(
            f"{user.username} is disabled, so a new password would not sign them in. "
            "Enable the login first."
        )

    chosen = password or new_password()
    user.password_hash = hash_password(chosen)
    await session.execute(delete(AuthToken).where(AuthToken.user_id == user.id))
    await session.commit()
    return chosen


async def set_active(session: AsyncSession, user_id: uuid.UUID, active: bool) -> User:
    """Turn a login off or on. Off refuses a new sign-in and drops the live token."""
    user = await session.get(User, user_id)
    if user is None:
        raise NotFound("No such user.")
    if user.is_superuser and not active:
        # One is allowed to go so a compromised account can be shut off; the
        # last one is not, because nothing could then reach the console.
        others = await session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.is_superuser.is_(True), User.is_active.is_(True), User.id != user.id)
        )
        if not others:
            raise AdminError("That is the only superuser left, so nothing could run the console.")

    user.is_active = active
    if not active:
        await session.execute(delete(AuthToken).where(AuthToken.user_id == user.id))
    await session.commit()
    return user


async def add_member(
    session: AsyncSession, campaign_id: uuid.UUID, user_id: uuid.UUID
) -> CampaignMember:
    """Put somebody on a campaign, in the capacity their login carries.

    The place comes from `users.role`. Every permission check reads that column,
    so a membership row saying anything else would name a capacity the member
    does not have.
    """
    campaign = await session.get(Campaign, campaign_id)
    if campaign is None:
        raise NotFound("No such campaign.")
    user = await session.get(User, user_id)
    if user is None:
        raise AdminError("No such user.")
    refusal = await membership_refusal(session, user, campaign_id)
    if refusal is not None:
        raise AdminError(refusal)

    existing = await session.scalar(
        select(CampaignMember).where(
            CampaignMember.campaign_id == campaign_id, CampaignMember.user_id == user_id
        )
    )
    if existing is not None:
        existing.role = user.role
        await session.commit()
        return existing

    member = CampaignMember(campaign_id=campaign_id, user_id=user_id, role=user.role)
    session.add(member)
    await session.commit()
    return member


async def rename_campaign(session: AsyncSession, campaign_id: uuid.UUID, title: str) -> Campaign:
    """Change what a campaign is called. Nothing else about it moves."""
    campaign = await session.get(Campaign, campaign_id)
    if campaign is None:
        raise NotFound("No such campaign.")
    cleaned = title.strip()
    if not cleaned:
        raise AdminError("A campaign needs a name.")

    campaign.title = cleaned
    await session.commit()
    return campaign


async def logins_deleted_with(session: AsyncSession, campaign_id: uuid.UUID) -> list[User]:
    """The logins deleting this campaign deletes, by username.

    Everyone on it or on its ground team, whatever other campaigns they are on,
    except a superuser.
    """
    on_it = select(CampaignMember.user_id).where(CampaignMember.campaign_id == campaign_id)
    on_the_ground = select(Mobilizer.user_id).where(
        Mobilizer.campaign_id == campaign_id, Mobilizer.user_id.is_not(None)
    )
    return list(
        (
            await session.execute(
                select(User)
                .where(User.id.in_(on_it.union(on_the_ground)), User.is_superuser.is_(False))
                .order_by(User.username)
            )
        ).scalars()
    )


async def delete_campaign(session: AsyncSession, campaign_id: uuid.UUID) -> list[str]:
    """Delete a campaign, everything on it, and `logins_deleted_with` it.

    Returns the usernames deleted.
    """
    campaign = await session.get(Campaign, campaign_id)
    if campaign is None:
        raise NotFound("No such campaign.")

    people = await logins_deleted_with(session, campaign_id)
    usernames = [person.username for person in people]
    # The database's ON DELETE rules take the tokens, memberships, targets,
    # mobilizers, events and supporters.
    if people:
        await session.execute(delete(User).where(User.id.in_([person.id for person in people])))
    await session.execute(delete(Campaign).where(Campaign.id == campaign_id))
    await session.commit()
    return usernames


async def remove_member(session: AsyncSession, campaign_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Take somebody off a campaign. Their login and their work stay."""
    campaign = await session.get(Campaign, campaign_id)
    if campaign is None:
        raise NotFound("No such campaign.")
    place = await session.scalar(
        select(CampaignMember.role).where(
            CampaignMember.campaign_id == campaign_id, CampaignMember.user_id == user_id
        )
    )
    if place is UserRole.CANDIDATE:
        raise AdminError("That is the candidate this campaign is for; delete the campaign instead.")

    removed = await session.execute(
        delete(CampaignMember).where(
            CampaignMember.campaign_id == campaign_id, CampaignMember.user_id == user_id
        )
    )
    await session.commit()
    if not removed.rowcount:
        raise AdminError("They are not on that campaign.")


async def _username_taken(session: AsyncSession, username: str) -> bool:
    """Whether the name is gone. Advisory: the unique constraint is the ruling."""
    return await session.scalar(select(User).where(User.username == username)) is not None


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
    """Create a login, and put it on a campaign when one is named.

    Returns the login and its password, which is generated here and never
    stored in the clear, so this is the only time it can be read.
    """
    if await _username_taken(session, username):
        raise AdminError(f"The username {username} is already taken.")

    campaign: Campaign | None = None
    ward: Ward | None = None
    if campaign_id is not None:
        campaign = await session.get(Campaign, campaign_id)
        if campaign is None:
            raise AdminError("No such campaign.")
        if role is UserRole.CANDIDATE:
            # A campaign is for one candidate. `campaign.candidate` is lazy and
            # not loaded here, so the name is read with a query.
            theirs = await session.scalar(
                select(User.username)
                .join(CampaignMember, CampaignMember.user_id == User.id)
                .where(
                    CampaignMember.campaign_id == campaign.id,
                    CampaignMember.role == UserRole.CANDIDATE,
                )
            )
            raise AdminError(
                f"{campaign.title} is already {theirs}'s campaign. "
                "Create the aspirant on their own, then set a campaign up for them."
            )
        if role is UserRole.MOBILIZER:
            if ward_id is None:
                raise AdminError("A mobilizer needs a ward, or they sign in to nothing.")
            ward = await session.get(Ward, ward_id)
            if ward is None:
                raise AdminError("No such ward.")
            if not await ward_in_area(session, campaign, ward_id):
                raise AdminError(f"{ward.name} is not a ward {campaign.title} works.")
    elif role is UserRole.MOBILIZER:
        raise AdminError("A mobilizer needs a campaign and a ward, or they sign in to nothing.")

    password = new_password()
    created = User(
        username=username,
        role=role,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        password_hash=hash_password(password),
    )
    session.add(created)
    try:
        # The insert, not the lookup above, is what the unique constraint rules
        # on: two creates can both pass the check and arrive here.
        await session.flush()
    except IntegrityError as clash:
        await session.rollback()
        raise AdminError(f"The username {username} is already taken.") from clash

    if campaign is not None:
        refusal = await membership_refusal(session, created, campaign.id)
        if refusal is not None:  # pragma: no cover - a login made here is always eligible
            raise AdminError(refusal)
        member = CampaignMember(campaign_id=campaign.id, user_id=created.id, role=created.role)
        session.add(member)
        if ward is not None:
            session.add(
                Mobilizer(
                    campaign_id=campaign.id,
                    ward_id=ward.id,
                    user_id=created.id,
                    full_name=created.full_name or created.username,
                    phone=created.phone,
                )
            )

    await session.commit()
    return created, password
