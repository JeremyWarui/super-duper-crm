"""The party's coordination workspace: creating it, its coordinators' view of the member
register, and their recruitment links to the Join the Party form."""

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    Campaign,
    CampaignMember,
    OfficeLevel,
    PartyMember,
    PartyMemberStatus,
    RecruitmentCode,
    User,
    UserRole,
    WorkspaceKind,
)
from backend.schemas.campaign import SetupSummary
from backend.security import new_short_code
from backend.services import site
from backend.services.accounts import add_member
from backend.services.audit import record
from backend.services.errors import Refused
from backend.services.login_links import new_invited_login
from backend.services.permissions import Area
from backend.services.targets import generate_targets

PAGE_SIZE = 50
EXISTS = "The party already has its workspace."


async def workspace(session: AsyncSession) -> Campaign | None:
    return await session.scalar(select(Campaign).where(Campaign.kind == WorkspaceKind.PARTY))


async def build(
    session: AsyncSession, *, name: str, manager: dict
) -> tuple[Campaign, SetupSummary, User, str]:
    """The party workspace, its targets and its first Workspace Manager, without committing."""
    campaign = Campaign(
        title=f"{name} workspace"[:150], kind=WorkspaceKind.PARTY, office_level=OfficeLevel.NATIONAL
    )
    session.add(campaign)
    await session.flush()
    summary = await generate_targets(session, campaign)
    created, invite = await new_invited_login(session, role=UserRole.MANAGER, **manager)
    await add_member(session, campaign.id, created)
    return campaign, summary, created, invite


async def create(
    session: AsyncSession, *, actor: User, manager: dict
) -> tuple[Campaign, SetupSummary, User, str]:
    """Create the party workspace, a ward target across the country, and its first Workspace
    Manager login, which is sent an invite link."""
    if await workspace(session) is not None:
        raise Refused(EXISTS)
    name = (await site.read_settings(session)).name
    try:
        campaign, summary, created, invite = await build(session, name=name, manager=manager)
    except Refused:
        await session.rollback()
        raise
    except IntegrityError:
        await session.rollback()
        raise Refused(EXISTS) from None
    record(
        session,
        actor=actor,
        action="party_workspace.create",
        subject_type="campaign",
        subject_id=campaign.id,
        campaign_id=campaign.id,
        detail={"units": summary.units},
    )
    await session.commit()
    return campaign, summary, created, invite


async def coordinator(session: AsyncSession, user: User) -> CampaignMember | None:
    """The caller's coordinator place on the party workspace, or None."""
    if user.role is not UserRole.COORDINATOR:
        return None
    return await session.scalar(
        select(CampaignMember)
        .join(Campaign, Campaign.id == CampaignMember.campaign_id)
        .where(CampaignMember.user_id == user.id, Campaign.kind == WorkspaceKind.PARTY)
    )


async def members_in_area(
    session: AsyncSession, member: CampaignMember, area: Area, page: int, *, actor: User
) -> tuple[int, list[PartyMember]]:
    """One page of the party members living in the coordinator's area, by name; audited."""
    where = area.where(PartyMember.ward_id, PartyMember.registration_centre_id)
    total = await session.scalar(select(func.count(PartyMember.id)).where(where))
    rows = list(
        await session.scalars(
            select(PartyMember)
            .where(where)
            .options(selectinload(PartyMember.ward), selectinload(PartyMember.registration_centre))
            .order_by(PartyMember.full_name, PartyMember.id)
            .limit(PAGE_SIZE)
            .offset((page - 1) * PAGE_SIZE)
        )
    )
    record(
        session,
        actor=actor,
        action="members.area_read",
        subject_type="campaign_member",
        subject_id=member.id,
        campaign_id=member.campaign_id,
        detail={"page": page, "rows": len(rows)},
    )
    await session.commit()
    return total or 0, rows


async def _active_code(session: AsyncSession, member: CampaignMember) -> RecruitmentCode | None:
    return await session.scalar(
        select(RecruitmentCode).where(
            RecruitmentCode.campaign_member_id == member.id, RecruitmentCode.active.is_(True)
        )
    )


async def recruitment(
    session: AsyncSession, member: CampaignMember, *, replace: bool, actor: User
) -> tuple[str, dict[PartyMemberStatus, int]]:
    """The coordinator's active recruitment code, made on first ask or replaced, and how many
    applicants each status holds among those it brought."""
    active = await _active_code(session, member)
    if active is None or replace:
        await session.execute(
            update(RecruitmentCode)
            .where(RecruitmentCode.campaign_member_id == member.id)
            .values(active=False)
        )
        active = RecruitmentCode(campaign_member_id=member.id, code=new_short_code())
        session.add(active)
        record(
            session,
            actor=actor,
            action="recruitment.code",
            subject_type="campaign_member",
            subject_id=member.id,
            campaign_id=member.campaign_id,
            detail={"replaced": replace},
        )
        try:
            await session.commit()
        except IntegrityError:
            # Another request issued the code a moment ago; theirs stands.
            await session.rollback()
            active = await _active_code(session, member)
    counts = dict(
        (
            await session.execute(
                select(PartyMember.status, func.count())
                .where(PartyMember.recruited_by_id == member.id)
                .group_by(PartyMember.status)
            )
        ).all()
    )
    return active.code, {status: counts.get(status, 0) for status in PartyMemberStatus}


async def recruiter(session: AsyncSession, code: str | None) -> uuid.UUID | None:
    """The coordinator place an active recruitment code belongs to, or None for any other code
    and for one whose coordinator is off the party workspace or turned off."""
    if not code:
        return None
    return await session.scalar(
        select(RecruitmentCode.campaign_member_id)
        .join(CampaignMember, CampaignMember.id == RecruitmentCode.campaign_member_id)
        .join(Campaign, Campaign.id == CampaignMember.campaign_id)
        .join(User, User.id == CampaignMember.user_id)
        .where(
            RecruitmentCode.code == code,
            RecruitmentCode.active.is_(True),
            Campaign.kind == WorkspaceKind.PARTY,
            CampaignMember.role == UserRole.COORDINATOR,
            User.is_active.is_(True),
        )
    )
