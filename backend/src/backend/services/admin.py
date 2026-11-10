"""Operations across every campaign, for a superuser through the console or the command line."""

import uuid

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.session import get_or_refuse
from backend.models import (
    Aspirant,
    Campaign,
    CampaignMember,
    Event,
    LinkPurpose,
    Mobilizer,
    PartyMember,
    PartyMemberStatus,
    PartyRole,
    PartyRoleName,
    RegistrationCentre,
    Supporter,
    Target,
    User,
    UserKind,
    UserRole,
)
from backend.schemas.admin import (
    AdminCampaignRead,
    AdminCentreRead,
    AdminUserRead,
    AdminWardRead,
    MemberRead,
    Totals,
)
from backend.schemas.campaign import SetupSummary
from backend.security import hash_password, new_password
from backend.services.accounts import add_member as join
from backend.services.accounts import (
    add_mobilizer,
    clean_email,
    leave,
    logins_on,
    member_of,
    sign_out,
    user_named,
    user_with_email,
)
from backend.services.audit import record
from backend.services.campaigns import build_campaign
from backend.services.errors import NotFound, Refused
from backend.services.login_links import new_invited_login, send_link
from backend.services.strategy import read_strategy
from backend.services.targets import require_ward, wards_in_area

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


async def _login_with_roles(session: AsyncSession, user_id: uuid.UUID) -> User:
    """The login with its party offices freshly loaded; NotFound when missing."""
    return await get_or_refuse(
        session,
        User,
        user_id,
        "user",
        options=[selectinload(User.party_roles)],
        populate_existing=True,
    )


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
    needed_by = {
        row[0]: row[1] or 0
        for row in await session.execute(
            select(Target.campaign_id, func.sum(Target.votes_needed))
            .where(Target.campaign_id.in_(ids))
            .group_by(Target.campaign_id)
        )
    }
    centres: dict[uuid.UUID, list[AdminCentreRead]] = {}
    for cid, centre in await session.execute(
        select(Target.campaign_id, RegistrationCentre)
        .join(RegistrationCentre, RegistrationCentre.id == Target.registration_centre_id)
        .where(Target.campaign_id.in_(ids))
        .order_by(RegistrationCentre.name)
    ):
        centres.setdefault(cid, []).append(
            AdminCentreRead(id=centre.id, name=centre.name, ward=centre.ward_id)
        )
    # Votes committed are read from the strategy, so both screens show one number.
    votes = {}
    for cid in ids:
        strategy = await read_strategy(session, campaign_ids=frozenset({cid}), campaign_id=cid)
        votes[cid] = (needed_by.get(cid, 0), strategy.committed)

    rows = []
    for campaign in found:
        members = sorted(campaign.members, key=lambda m: (m.role.value, m.user.username))
        needed, committed = votes.get(campaign.id, (0, 0))
        rows.append(
            AdminCampaignRead(
                id=campaign.id,
                title=campaign.title,
                office_level=campaign.seat_label,
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
                centres=centres.get(campaign.id, []),
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
    limit: int | None = None,
    offset: int = 0,
) -> list[AdminUserRead]:
    """Every login matching the filters by username, with the title of the campaign it is on.

    A login is on one campaign at most, so `limit` and `offset` page over logins.
    """
    statement = (
        select(User, Campaign.title)
        .outerjoin(CampaignMember, CampaignMember.user_id == User.id)
        .outerjoin(Campaign, Campaign.id == CampaignMember.campaign_id)
        .options(selectinload(User.party_roles), selectinload(User.party_member))
        .order_by(User.username, User.id)
        .offset(offset)
        .limit(limit)
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
            kind=login.kind,
            is_active=login.is_active,
            is_superuser=login.is_superuser,
            last_login_at=login.last_login_at.isoformat() if login.last_login_at else None,
            campaign=title,
            party_roles=[held.role for held in login.party_roles],
            party_member=login.party_member,
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


async def set_password(session: AsyncSession, user_id: uuid.UUID, password: str | None) -> str:
    """Give a login a password and sign out its session; for the operator's command line only."""
    login = await get_or_refuse(session, User, user_id, "user")
    chosen = password or new_password()
    login.password_hash = hash_password(chosen)
    await sign_out(session, login.id)
    record(
        session, actor=None, action="user.set_password", subject_type="user", subject_id=login.id
    )
    await session.commit()
    return chosen


async def reset_password(session: AsyncSession, user_id: uuid.UUID, *, actor: User) -> str:
    """Send a login a link to choose a new password; returns how it went out.

    Nobody else sets or sees the password. The login keeps working until the link is used.
    """
    login = await get_or_refuse(session, User, user_id, "user")
    if not login.is_active:
        raise Refused(
            f"{login.username} is disabled, so a reset link would not sign them in. "
            "Enable the login first."
        )
    sent = await send_link(session, login, LinkPurpose.RESET)
    if sent == "none":
        raise Refused(f"{login.username} has no email to send a reset link to.")
    record(
        session,
        actor=actor,
        action="user.reset_password",
        subject_type="user",
        subject_id=login.id,
    )
    await session.commit()
    return sent


async def set_active(
    session: AsyncSession, user_id: uuid.UUID, active: bool, *, actor: User | None
) -> User:
    """Turn a login on or off; off signs it out. The last active superuser stays on."""
    login = await get_or_refuse(session, User, user_id, "user")
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
        await sign_out(session, login.id)
    record(
        session,
        actor=actor,
        action="user.activate" if active else "user.deactivate",
        subject_type="user",
        subject_id=login.id,
    )
    await session.commit()
    return login


async def set_email(
    session: AsyncSession, user_id: uuid.UUID, email: str, *, actor: User | None
) -> User:
    """Change the email a login signs in with and gets its links at."""
    login = await get_or_refuse(session, User, user_id, "user")
    email = clean_email(email)
    holder = await user_with_email(session, email)
    if holder is not None and holder.id != login.id:
        raise Refused(f"The email {email} already belongs to another login.")
    login.email = email
    record(session, actor=actor, action="user.email", subject_type="user", subject_id=login.id)
    await session.commit()
    return login


async def add_member(
    session: AsyncSession, campaign_id: uuid.UUID, user_id: uuid.UUID, *, actor: User | None
) -> CampaignMember:
    target = await get_or_refuse(session, Campaign, campaign_id, "campaign")
    login = await session.get(User, user_id)
    if login is None:
        raise Refused("No such user.")
    member = await join(session, target.id, login)
    record(
        session,
        actor=actor,
        action="member.add",
        subject_type="user",
        subject_id=login.id,
        campaign_id=target.id,
        detail={"role": member.role.value},
    )
    await session.commit()
    return member


async def remove_member(
    session: AsyncSession, campaign_id: uuid.UUID, user_id: uuid.UUID, *, actor: User | None
) -> None:
    """Take somebody off a campaign, freeing a mobilizer's ground row there; the login stays."""
    await get_or_refuse(session, Campaign, campaign_id, "campaign")
    place = await member_of(session, campaign_id, user_id)
    if place is None:
        raise Refused("They are not on that campaign.")
    if place.role is UserRole.CANDIDATE:
        raise Refused("That is the candidate this campaign is for; delete the campaign instead.")
    await leave(session, campaign_id, user_id)
    await session.execute(
        update(Mobilizer)
        .where(Mobilizer.campaign_id == campaign_id, Mobilizer.user_id == user_id)
        .values(user_id=None)
    )
    record(
        session,
        actor=actor,
        action="member.remove",
        subject_type="user",
        subject_id=user_id,
        campaign_id=campaign_id,
        detail={"role": place.role.value},
    )
    await session.commit()


async def rename_campaign(
    session: AsyncSession, campaign_id: uuid.UUID, title: str, *, actor: User | None
) -> Campaign:
    renamed = await get_or_refuse(session, Campaign, campaign_id, "campaign")
    if not title.strip():
        raise Refused("A campaign needs a name.")
    renamed.title = title.strip()
    record(
        session,
        actor=actor,
        action="campaign.rename",
        subject_type="campaign",
        subject_id=renamed.id,
        campaign_id=renamed.id,
    )
    await session.commit()
    return renamed


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


async def delete_campaign(
    session: AsyncSession, campaign_id: uuid.UUID, *, actor: User | None
) -> list[str]:
    """Delete a campaign, everything on it and its people's logins; returns their usernames."""
    await get_or_refuse(session, Campaign, campaign_id, "campaign")
    aspirant = await session.scalar(select(Aspirant.id).where(Aspirant.campaign_id == campaign_id))
    gone = await remove_campaign(session, campaign_id)
    detail: dict = {"logins": len(gone)}
    if aspirant is not None:
        detail["aspirant"] = str(aspirant)
    record(
        session,
        actor=actor,
        action="campaign.delete",
        subject_type="campaign",
        subject_id=campaign_id,
        campaign_id=campaign_id,
        detail=detail,
    )
    await session.commit()
    return gone


async def build_workspace(
    session: AsyncSession,
    *,
    aspirant: dict,
    manager: dict | None = None,
    party_member_id: uuid.UUID | None = None,
    **campaign_fields,
) -> tuple[Campaign, SetupSummary, list[tuple[User, str]]]:
    """Build a campaign, its targets and its aspirant's and manager's logins, without committing.

    `party_member_id` links the aspirant's login to their party member. A username clash rolls
    the session back, so the caller treats any `Refused` as the end of its transaction.
    """
    if manager is not None and manager["username"] == aspirant["username"]:
        raise Refused("The aspirant and the manager need different usernames.")
    created, summary = await build_campaign(session, **campaign_fields)
    logins = [await new_invited_login(session, role=UserRole.CANDIDATE, **aspirant)]
    logins[0][0].party_member_id = party_member_id
    if manager is not None:
        logins.append(await new_invited_login(session, role=UserRole.MANAGER, **manager))
    for login, _ in logins:
        await join(session, created.id, login)
    return created, summary, logins


async def create_user(
    session: AsyncSession,
    *,
    actor: User | None,
    username: str,
    role: UserRole | None,
    first_name: str = "",
    last_name: str = "",
    email: str = "",
    phone: str = "",
    campaign_id: uuid.UUID | None = None,
    ward_id: uuid.UUID | None = None,
    centre_id: uuid.UUID | None = None,
) -> tuple[User, str]:
    """Create a login, on a campaign when one is named; returns it and how its invite went out.

    A `role` of None makes a staff login, which stays off every campaign.
    """
    if role is None and (campaign_id or ward_id or centre_id):
        raise Refused("A staff login has no campaign role, so it cannot be put on a campaign.")
    target = await session.get(Campaign, campaign_id) if campaign_id is not None else None
    if campaign_id is not None and target is None:
        raise Refused("No such campaign.")
    mobilizer_ward: uuid.UUID | None = None
    if role is UserRole.MOBILIZER:
        if target is None:
            raise Refused("A mobilizer needs a campaign and a ward, or they sign in to nothing.")
        if ward_id is None:
            raise Refused("A mobilizer needs a ward, or they sign in to nothing.")
        await require_ward(session, target, ward_id)
        mobilizer_ward = ward_id
    if role is UserRole.CANDIDATE:
        raise Refused(
            "An aspirant gets their login with their workspace, from Aspirants or at setup."
        )

    try:
        created, invite = await new_invited_login(
            session,
            username=username,
            role=role,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
        )
        if mobilizer_ward is not None:
            await add_mobilizer(session, target, mobilizer_ward, created, centre_id=centre_id)
        elif target is not None:
            await join(session, target.id, created)
    except Refused:
        await session.rollback()
        raise
    record(
        session,
        actor=actor,
        action="user.create",
        subject_type="user",
        subject_id=created.id,
        campaign_id=target.id if target is not None else None,
        detail={"role": role.value if role else None},
    )
    await session.commit()
    return created, invite


async def grant_party_role(
    session: AsyncSession, user_id: uuid.UUID, role: PartyRoleName, *, actor: User | None
) -> None:
    """Give a staff login a party office."""
    login = await _login_with_roles(session, user_id)
    if login.is_superuser:
        raise Refused("A superuser reaches the party through the console and needs no office.")
    if login.role is not None:
        raise Refused(
            f"{login.username} works on a campaign, and a login is campaign or party, not both. "
            "Create a staff login for the party office."
        )
    if login.kind is UserKind.MEMBER:
        raise Refused(
            f"{login.username} is a member's own login. Create a staff login, link it to "
            "their membership, and give the office to that."
        )
    if any(held.role is role for held in login.party_roles):
        raise Refused(f"{login.username} is already a {role.label}.")
    member = (
        await session.get(PartyMember, login.party_member_id) if login.party_member_id else None
    )
    if member is None or member.status is not PartyMemberStatus.APPROVED:
        raise Refused(f"Link {login.username} to their approved party member first.")
    login.party_roles.append(PartyRole(role=role))
    record(
        session,
        actor=actor,
        action="party_role.grant",
        subject_type="user",
        subject_id=login.id,
        detail={"role": role.value},
    )
    await session.commit()


async def revoke_party_role(
    session: AsyncSession, user_id: uuid.UUID, role: PartyRoleName, *, actor: User | None
) -> None:
    """Take a party office from a login."""
    login = await _login_with_roles(session, user_id)
    held = next((item for item in login.party_roles if item.role is role), None)
    if held is None:
        raise NotFound(f"{login.username} is not a {role.label}.")
    login.party_roles.remove(held)
    record(
        session,
        actor=actor,
        action="party_role.revoke",
        subject_type="user",
        subject_id=login.id,
        detail={"role": role.value},
    )
    await session.commit()


async def link_party_member(
    session: AsyncSession, user_id: uuid.UUID, member_id: uuid.UUID | None, *, actor: User | None
) -> None:
    """Link a login to the party member it belongs to, or unlink it.

    An office holder stays linked to an approved member.
    """
    login = await _login_with_roles(session, user_id)
    member = await session.get(PartyMember, member_id) if member_id else None
    if member_id is not None and member is None:
        raise NotFound("No such member.")
    if login.party_roles and (member is None or member.status is not PartyMemberStatus.APPROVED):
        raise Refused(
            f"{login.username} holds a party office, so it stays linked to an approved member."
        )
    login.party_member_id = member_id
    record(
        session,
        actor=actor,
        action="user.party_member",
        subject_type="user",
        subject_id=login.id,
        detail={"member": str(member_id) if member_id else None},
    )
    await session.commit()
