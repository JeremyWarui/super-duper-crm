"""A campaign's own people: who is on it, its one manager, its coordinators and comms, and the
coordinators' areas."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Campaign,
    CampaignMember,
    CampaignMemberArea,
    User,
    UserRole,
)
from backend.services.accounts import add_member, leave, logins_on, member_of, sign_out
from backend.services.audit import record
from backend.services.errors import NotFound, Refused
from backend.services.login_links import new_invited_login
from backend.services.targets import require_centre, require_ward

ORDER = {role: rank for rank, role in enumerate(UserRole)}
# Roles the candidate and manager add from the Team page.
STAFF = frozenset({UserRole.COORDINATOR, UserRole.COMMS})


async def team(session: AsyncSession, campaign_id: uuid.UUID) -> list[User]:
    """The logins on a campaign by role, the aspirant first, then by username."""
    found = await logins_on(session, campaign_id)
    return sorted(found, key=lambda u: (ORDER.get(u.role, 3), u.username))


async def set_manager(
    session: AsyncSession, campaign: Campaign, details: dict, *, replace: bool, actor: User | None
) -> tuple[User, str, str | None]:
    """Give a campaign a new manager login and send it an invite link.

    With `replace` the sitting manager is taken off the campaign, turned off and signed out.
    Returns the new login, how its invite went out and the replaced manager's username.
    """
    sitting = next(iter(await logins_on(session, campaign.id, UserRole.MANAGER)), None)
    replaced = sitting.username if sitting is not None else None
    if sitting is not None and not replace:
        raise Refused(f"{campaign.title} already has a manager, {replaced}. Replace them instead.")
    try:
        created, invite = await new_invited_login(session, role=UserRole.MANAGER, **details)
        if sitting is not None:
            await leave(session, campaign.id, sitting.id)
            await sign_out(session, sitting.id)
            sitting.is_active = False
        await add_member(session, campaign.id, created)
    except Refused:
        await session.rollback()
        raise
    record(
        session,
        actor=actor,
        action="team.set_manager",
        subject_type="user",
        subject_id=created.id,
        campaign_id=campaign.id,
        detail={"replaced_user_id": str(sitting.id) if sitting is not None else None},
    )
    await session.commit()
    return created, invite, replaced


async def add_staff(
    session: AsyncSession, campaign: Campaign, role: UserRole, details: dict, *, actor: User
) -> tuple[User, str]:
    """Give a campaign a coordinator or comms login and send it an invite link."""
    if role not in STAFF:
        raise Refused("Only a coordinator or a comms officer is added here.")
    try:
        created, invite = await new_invited_login(session, role=role, **details)
        await add_member(session, campaign.id, created)
    except Refused:
        await session.rollback()
        raise
    record(
        session,
        actor=actor,
        action="team.add",
        subject_type="user",
        subject_id=created.id,
        campaign_id=campaign.id,
        detail={"role": role.value},
    )
    await session.commit()
    return created, invite


async def remove_staff(
    session: AsyncSession, campaign: Campaign, user_id: uuid.UUID, *, actor: User
) -> None:
    """Take a coordinator or comms officer off the campaign; their login is turned off and
    signed out."""
    member = await _member(session, campaign.id, user_id)
    if member.role not in STAFF:
        raise Refused("Only a coordinator or a comms officer is taken off here.")
    person = await session.get(User, user_id)
    await session.delete(member)
    await sign_out(session, user_id)
    person.is_active = False
    record(
        session,
        actor=actor,
        action="team.remove",
        subject_type="user",
        subject_id=user_id,
        campaign_id=campaign.id,
        detail={"role": member.role.value},
    )
    await session.commit()


async def _member(
    session: AsyncSession, campaign_id: uuid.UUID, user_id: uuid.UUID
) -> CampaignMember:
    member = await member_of(session, campaign_id, user_id)
    if member is None:
        raise NotFound("No such person on this campaign.")
    return member


async def areas(
    session: AsyncSession, campaign_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    """A team member's area: its wards and its registration centres."""
    member = await _member(session, campaign_id, user_id)
    rows = (
        await session.execute(
            select(CampaignMemberArea.ward_id, CampaignMemberArea.registration_centre_id).where(
                CampaignMemberArea.campaign_member_id == member.id
            )
        )
    ).all()
    return (
        sorted(w for w, _ in rows if w is not None),
        sorted(c for _, c in rows if c is not None),
    )


async def set_areas(
    session: AsyncSession,
    campaign: Campaign,
    user_id: uuid.UUID,
    wards: list[uuid.UUID],
    centres: list[uuid.UUID],
    *,
    actor: User,
) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    """Replace a coordinator's wards and centres; each must lie inside the campaign's seat."""
    member = await _member(session, campaign.id, user_id)
    if member.role is not UserRole.COORDINATOR:
        raise Refused("Only a coordinator has an area.")
    wards, centres = sorted(set(wards)), sorted(set(centres))
    for ward_id in wards:
        await require_ward(session, campaign, ward_id)
    for centre_id in centres:
        await require_centre(session, campaign, centre_id)
    await session.execute(
        delete(CampaignMemberArea).where(CampaignMemberArea.campaign_member_id == member.id)
    )
    session.add_all(
        [CampaignMemberArea(campaign_member_id=member.id, ward_id=w) for w in wards]
        + [
            CampaignMemberArea(campaign_member_id=member.id, registration_centre_id=c)
            for c in centres
        ]
    )
    record(
        session,
        actor=actor,
        action="team.areas",
        subject_type="user",
        subject_id=user_id,
        campaign_id=campaign.id,
        detail={"wards": len(wards), "centres": len(centres)},
    )
    await session.commit()
    return wards, centres
