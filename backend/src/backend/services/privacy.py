"""Erasure on request, data subject requests, and closing a campaign after the election.

Erasing blanks a row's personal fields and keeps the row, so counts and totals stay right. The
audit row it writes names only the row, the officer and the time.
"""

import calendar
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import Select, false, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import get_settings
from backend.db.session import get_or_refuse
from backend.models import (
    Campaign,
    CampaignMember,
    DataRequest,
    DataRequestKind,
    DataRequestStatus,
    Mobilizer,
    PartyMember,
    PartyMemberStatus,
    RegistrationStatus,
    SmsLog,
    Supporter,
    TeamRegistration,
    User,
    VolunteerProfile,
    VolunteerStatus,
    WorkspaceKind,
)
from backend.schemas.privacy import DataRequestCreate, DataRequestUpdate
from backend.services import texting
from backend.services.access import READ_ONLY
from backend.services.audit import record
from backend.services.errors import Refused, refuse_erased

ERASED = "Erased"
# Days to answer, from the Data Protection (General) Regulations 2021 (regs 9, 10 and 12).
DUE_DAYS = {
    DataRequestKind.ACCESS: 7,
    DataRequestKind.CORRECTION: 14,
    DataRequestKind.ERASURE: 14,
}
CLOSED = READ_ONLY.reason


def _now() -> datetime:
    return datetime.now(UTC)


def placeholder(row_id: uuid.UUID) -> str:
    """A stand-in for a unique phone or ID number; never a real one."""
    return f"~{row_id.hex[:19]}"


def _audit(
    session: AsyncSession,
    actor: User,
    kind: str,
    row_id: uuid.UUID,
    campaign_id: uuid.UUID | None,
) -> None:
    record(
        session,
        actor=actor,
        action=f"{kind}.erase",
        subject_type=kind,
        subject_id=row_id,
        campaign_id=campaign_id,
    )


async def _forget_texts(session: AsyncSession, campaign_id: uuid.UUID | None, phone: str) -> None:
    """Blank the number on the texts this register sent; the counts of texts stay."""
    if not phone:
        return
    where = SmsLog.phone == phone
    where = where & (
        SmsLog.campaign_id.is_(None) if campaign_id is None else SmsLog.campaign_id == campaign_id
    )
    await session.execute(
        update(SmsLog).where(where).values(phone="").execution_options(synchronize_session=False)
    )


async def _forget_login(session: AsyncSession, user_id: uuid.UUID | None) -> None:
    """Blank a login left behind by someone erased; a login still on a campaign is kept."""
    if user_id is None:
        return
    user = await session.scalar(
        select(User).where(User.id == user_id).options(selectinload(User.party_roles))
    )
    if user is None or user.is_superuser or user.party_roles:
        return
    if await session.scalar(select(CampaignMember.id).where(CampaignMember.user_id == user_id)):
        return
    user.username = f"erased-{user_id.hex[:12]}"
    user.email = ""
    user.first_name = ""
    user.last_name = ""
    user.phone = ""
    user.password_hash = ""
    user.is_active = False
    user.pending = False


async def erase_supporter(session: AsyncSession, supporter: Supporter, *, actor: User) -> None:
    """Blank one supporter; their ward, centre, mobilizer and support level stay counted."""
    refuse_erased(supporter)
    await _forget_texts(session, supporter.campaign_id, supporter.phone)
    supporter.full_name = ERASED
    supporter.phone = ""
    supporter.withdraw_code = None
    supporter.erased_at = _now()
    _audit(session, actor, "supporter", supporter.id, supporter.campaign_id)


async def erase_volunteer(session: AsyncSession, profile: VolunteerProfile, *, actor: User) -> None:
    """Blank a withdrawn volunteer; the row stays, withdrawn."""
    refuse_erased(profile)
    if profile.status is not VolunteerStatus.WITHDRAWN:
        raise Refused("Only a withdrawn volunteer can be erased.")
    await _forget_texts(session, profile.campaign_id, profile.phone)
    _blank_volunteer(profile)
    _audit(session, actor, "volunteer", profile.id, profile.campaign_id)


def _blank_volunteer(profile: VolunteerProfile) -> None:
    profile.first_name = ERASED
    profile.last_name = ""
    profile.phone = placeholder(profile.id)
    profile.email = None
    profile.profession = None
    profile.profession_other = ""
    profile.interests = []
    profile.interest_other = ""
    profile.availability_notes = None
    profile.withdraw_code = None
    profile.erased_at = _now()


async def erase_member(session: AsyncSession, member: PartyMember, *, actor: User) -> None:
    """Blank a withdrawn or rejected party member, their volunteer profile and their account."""
    refuse_erased(member)
    if member.status not in (PartyMemberStatus.WITHDRAWN, PartyMemberStatus.REJECTED):
        raise Refused("Only a withdrawn or rejected member can be erased.")
    await _forget_texts(session, None, member.phone)
    profile = await session.scalar(
        select(VolunteerProfile).where(VolunteerProfile.member_id == member.id)
    )
    if profile is not None and profile.erased_at is None:
        _blank_volunteer(profile)
    login = await session.scalar(select(User.id).where(User.party_member_id == member.id))
    member.full_name = ERASED
    member.first_name = None
    member.phone = placeholder(member.id)
    member.email = None
    member.status_reason = None
    member.withdraw_code = None
    member.erased_at = _now()
    await _forget_login(session, login)
    _audit(session, actor, "party_member", member.id, None)


async def on_team(session: AsyncSession, registration: TeamRegistration) -> bool:
    """Whether the person behind this registration still works on its campaign."""
    if registration.status is RegistrationStatus.REJECTED or registration.user_id is None:
        return False
    return (
        await session.scalar(
            select(CampaignMember.id).where(
                CampaignMember.user_id == registration.user_id,
                CampaignMember.campaign_id == registration.campaign_id,
            )
        )
    ) is not None


async def erase_registration(
    session: AsyncSession, registration: TeamRegistration, *, actor: User
) -> None:
    """Blank a mobilizer's or agent's sign-up, ID number included, once they are off the team."""
    refuse_erased(registration)
    if registration.status is RegistrationStatus.PENDING or await on_team(session, registration):
        raise Refused("Only someone who was turned down or has left the team can be erased.")
    await _forget_texts(session, registration.campaign_id, registration.phone)
    left_behind = Mobilizer.user_id == registration.user_id if registration.user_id else false()
    await session.execute(
        update(Mobilizer)
        .where(
            Mobilizer.campaign_id == registration.campaign_id,
            left_behind | (Mobilizer.user_id.is_(None) & (Mobilizer.phone == registration.phone)),
        )
        .values(full_name=ERASED, phone="")
        .execution_options(synchronize_session=False)
    )
    registration.first_name = ERASED
    registration.last_name = ""
    registration.phone = placeholder(registration.id)
    registration.email = ""
    registration.id_number = placeholder(registration.id)
    registration.reason = ""
    registration.erased_at = _now()
    await _forget_login(session, registration.user_id)
    _audit(session, actor, "team_registration", registration.id, registration.campaign_id)


def left_team(campaign_id: uuid.UUID) -> Select:
    """The campaign's sign-ups whose person was turned down or is no longer on the team."""
    still_member = (
        select(CampaignMember.id)
        .where(
            CampaignMember.user_id == TeamRegistration.user_id,
            CampaignMember.campaign_id == TeamRegistration.campaign_id,
        )
        .exists()
    )
    return (
        select(TeamRegistration)
        .where(
            TeamRegistration.campaign_id == campaign_id,
            TeamRegistration.erased_at.is_(None),
            TeamRegistration.status != RegistrationStatus.PENDING,
            (TeamRegistration.status == RegistrationStatus.REJECTED) | ~still_member,
        )
        .order_by(TeamRegistration.created_at.desc())
    )


# Withdrawal links for supporters.


def withdrawal_url(code: str) -> str:
    return get_settings().url(f"/withdraw/{code}")


async def text_withdrawal(
    session: AsyncSession, supporter: Supporter, campaign: Campaign, *, actor: User
) -> None:
    """Text a supporter their withdrawal link through the one send path; the caller commits."""
    if not supporter.phone or not supporter.withdraw_code:
        raise Refused("This supporter has no phone number to text.")
    body = (
        f"{campaign.title} has your name on its supporter register. "
        f"To remove your details at any time, open {withdrawal_url(supporter.withdraw_code)}"
    )
    await texting.send(
        session,
        [supporter.phone],
        body,
        purpose="withdrawal_link",
        sender=actor,
        campaign_id=campaign.id,
    )


# Data subject requests.


def due_on(kind: DataRequestKind, received: date) -> date:
    return received + timedelta(days=DUE_DAYS[kind])


def requests(campaign_id: uuid.UUID | None) -> Select:
    """Open requests first, the soonest due on top; then the answered, newest first."""
    scope = (
        DataRequest.campaign_id.is_(None)
        if campaign_id is None
        else DataRequest.campaign_id == campaign_id
    )
    return (
        select(DataRequest)
        .where(scope)
        .order_by(
            (DataRequest.status == DataRequestStatus.DONE).asc(),
            DataRequest.due_on.asc(),
            DataRequest.created_at.desc(),
        )
    )


def log_request(
    session: AsyncSession,
    campaign_id: uuid.UUID | None,
    payload: DataRequestCreate,
    *,
    actor: User,
) -> DataRequest:
    """Add a request; its due date is the legal one unless the officer set another."""
    kind = DataRequestKind(payload.kind)
    received = payload.received_on or _now().date()
    row = DataRequest(
        campaign_id=campaign_id,
        kind=kind,
        requester_name=payload.requester_name,
        requester_contact=payload.requester_contact,
        details=payload.details,
        received_on=received,
        due_on=payload.due_on or due_on(kind, received),
        logged_by_id=actor.id,
    )
    session.add(row)
    return row


async def find_request(
    session: AsyncSession, campaign_id: uuid.UUID | None, request_id: uuid.UUID
) -> DataRequest:
    row = await get_or_refuse(
        session, DataRequest, request_id, "request", match={"campaign_id": campaign_id}
    )
    return row


def update_request(row: DataRequest, payload: DataRequestUpdate, *, actor: User) -> None:
    """Change the due date or the answer; marking it answered records who and when."""
    fields = payload.model_fields_set
    if "due_on" in fields and payload.due_on is not None:
        row.due_on = payload.due_on
    if "answer" in fields and payload.answer is not None:
        row.answer = payload.answer
    if "status" in fields and payload.status is not None:
        to = DataRequestStatus(payload.status)
        if to is DataRequestStatus.DONE and not row.answer.strip():
            raise Refused("Write down how the request was answered first.")
        if to is not row.status:
            row.status = to
            done = to is DataRequestStatus.DONE
            row.answered_by_id = actor.id if done else None
            row.answered_at = _now() if done else None


# Closing a campaign.


def erase_from(campaign: Campaign) -> datetime | None:
    """When supporter data may be erased: the retention period after closing."""
    if campaign.closed_at is None:
        return None
    return add_months(campaign.closed_at, campaign.retention_months)


def add_months(when: datetime, months: int) -> datetime:
    """The same day `months` later, or the month's last day when it has fewer days."""
    year, month = divmod(when.month - 1 + months, 12)
    year += when.year
    day = min(when.day, calendar.monthrange(year, month + 1)[1])
    return when.replace(year=year, month=month + 1, day=day)


def set_retention(campaign: Campaign, months: int, *, actor: User) -> None:
    if campaign.closed_at is not None:
        raise Refused("The retention period is fixed once the campaign is closed.")
    campaign.retention_months = months


def close(session: AsyncSession, campaign: Campaign, *, actor: User) -> None:
    """Make the workspace read-only for good."""
    if campaign.kind is WorkspaceKind.PARTY:
        raise Refused("The party workspace is never closed.")
    if campaign.closed_at is not None:
        raise Refused("This campaign is already closed.")
    campaign.closed_at = _now()
    campaign.closed_by_id = actor.id
    record(
        session,
        actor=actor,
        action="campaign.close",
        subject_type="campaign",
        subject_id=campaign.id,
        campaign_id=campaign.id,
        detail={"retention_months": campaign.retention_months},
    )


async def erase_supporters(session: AsyncSession, campaign: Campaign, *, actor: User) -> int:
    """Blank every supporter of a closed campaign once its retention period is over."""
    after = erase_from(campaign)
    if after is None:
        raise Refused("Close the campaign first.")
    if _now() < after:
        raise Refused(f"Supporter data is kept until {after:%d %B %Y}.")
    if campaign.supporters_erased_at is not None:
        raise Refused("Supporter data was already erased.")
    phones = select(Supporter.phone).where(
        Supporter.campaign_id == campaign.id, Supporter.phone != ""
    )
    await session.execute(
        update(SmsLog)
        .where(SmsLog.campaign_id == campaign.id, SmsLog.phone.in_(phones))
        .values(phone="")
        .execution_options(synchronize_session=False)
    )
    erased = await session.execute(
        update(Supporter)
        .where(Supporter.campaign_id == campaign.id, Supporter.erased_at.is_(None))
        .values(full_name=ERASED, phone="", withdraw_code=None, erased_at=_now())
        .execution_options(synchronize_session=False)
    )
    campaign.supporters_erased_at = _now()
    record(
        session,
        actor=actor,
        action="supporters.erase_all",
        subject_type="campaign",
        subject_id=campaign.id,
        campaign_id=campaign.id,
        detail={"supporters": erased.rowcount},
    )
    return erased.rowcount
