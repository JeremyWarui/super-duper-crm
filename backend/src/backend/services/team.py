"""A campaign's own people: who is on it, its one manager, its coordinators and comms, and the
coordinators' areas."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    AuthToken,
    Campaign,
    CampaignMember,
    CampaignMemberArea,
    RegistrationCentre,
    User,
    UserRole,
)
from backend.services.accounts import add_member, new_login
from backend.services.audit import record
from backend.services.errors import NotFound, Refused
from backend.services.targets import ward_in_area

ORDER = {role: rank for rank, role in enumerate(UserRole)}
# Roles the candidate and manager add from the Team page.
STAFF = frozenset({UserRole.COORDINATOR, UserRole.COMMS})


async def team(session: AsyncSession, campaign_id: uuid.UUID) -> list[User]:
    """The logins on a campaign by role, the aspirant first, then by username."""
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
    session: AsyncSession, campaign: Campaign, details: dict, *, replace: bool, actor: User | None
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
    return created, password, replaced


async def add_staff(
    session: AsyncSession, campaign: Campaign, role: UserRole, details: dict, *, actor: User
) -> tuple[User, str]:
    """Give a campaign a coordinator or comms login, shown with its password once."""
    if role not in STAFF:
        raise Refused("Only a coordinator or a comms officer is added here.")
    try:
        created, password = await new_login(session, role=role, **details)
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
    return created, password


async def _member(
    session: AsyncSession, campaign_id: uuid.UUID, user_id: uuid.UUID
) -> CampaignMember:
    member = await session.scalar(
        select(CampaignMember).where(
            CampaignMember.campaign_id == campaign_id, CampaignMember.user_id == user_id
        )
    )
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
        if not await ward_in_area(session, campaign, ward_id):
            raise Refused("That ward is not one this campaign works.")
    for centre_id in centres:
        centre_ward = await session.scalar(
            select(RegistrationCentre.ward_id).where(RegistrationCentre.id == centre_id)
        )
        if centre_ward is None or not await ward_in_area(session, campaign, centre_ward):
            raise Refused("That registration centre is not one this campaign works.")
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
