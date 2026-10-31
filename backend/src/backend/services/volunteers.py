"""Volunteer profiles: the move table, officer moves, and the public volunteer requests."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, String, cast, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager
from sqlalchemy.orm.attributes import set_committed_value

from backend.models import (
    Constituency,
    ContactMethod,
    PartyMember,
    PartyMemberStatus,
    User,
    VolunteerInterest,
    VolunteerProfile,
    VolunteerStatus,
    Ward,
)
from backend.services.audit import record
from backend.services.consent import VOLUNTEER_WORDING
from backend.services.errors import NotFound, Refused

V = VolunteerStatus

VOLUNTEER_MOVES: dict[VolunteerStatus, frozenset[VolunteerStatus]] = {
    V.INTERESTED: frozenset({V.ACTIVE, V.WITHDRAWN}),
    V.ACTIVE: frozenset({V.INACTIVE, V.WITHDRAWN}),
    V.INACTIVE: frozenset({V.ACTIVE, V.WITHDRAWN}),
    V.WITHDRAWN: frozenset({V.INTERESTED}),
}

OFFICER_TARGETS = frozenset({V.ACTIVE, V.INACTIVE})


def check_move(frm: VolunteerStatus, to: VolunteerStatus) -> None:
    """Refuse a move the table does not list."""
    if to not in VOLUNTEER_MOVES[frm]:
        raise Refused(f"A {frm.label.lower()} volunteer cannot be moved to {to.label.lower()}.")


async def _set_status(
    session: AsyncSession, profile: VolunteerProfile, old: VolunteerStatus, **values
) -> None:
    """Write the change only if the row still has the status it was checked against."""
    changed = await session.execute(
        update(VolunteerProfile)
        .where(VolunteerProfile.id == profile.id, VolunteerProfile.status == old)
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        raise Refused("This volunteer's status changed meanwhile; reload and try again.")
    for name, value in values.items():
        set_committed_value(profile, name, value)


async def _fresh(session: AsyncSession, where) -> VolunteerProfile | None:
    """The profile matching `where`, read from the database rather than the session."""
    return await session.scalar(
        select(VolunteerProfile).where(where).execution_options(populate_existing=True)
    )


def _audit(
    session: AsyncSession,
    profile: VolunteerProfile,
    action: str,
    detail: dict,
    *,
    actor: User | None = None,
    actor_name: str = "public",
) -> None:
    record(
        session,
        actor=actor,
        actor_name=actor_name,
        action=action,
        subject_type="volunteer_profile",
        subject_id=profile.id,
        detail=detail,
    )


async def set_status(
    session: AsyncSession, profile: VolunteerProfile, to: VolunteerStatus, *, actor: User
) -> None:
    """An officer's move to active or inactive, audited; the caller commits."""
    old = profile.status
    if to not in OFFICER_TARGETS:
        raise Refused("An officer can only make a volunteer active or inactive.")
    check_move(old, to)
    if to is V.ACTIVE:
        member_status = await session.scalar(
            select(PartyMember.status)
            .where(PartyMember.id == profile.member_id)
            .execution_options(populate_existing=True)
        )
        if member_status is not PartyMemberStatus.APPROVED:
            raise Refused("Only an approved member can be an active volunteer.")
    await _set_status(session, profile, old, status=to)
    _audit(session, profile, "volunteer.status", {"from": old.value, "to": to.value}, actor=actor)


def set_notes(
    session: AsyncSession, profile: VolunteerProfile, notes: str | None, *, actor: User
) -> None:
    """Replace the officer's availability notes; the audit never holds the text."""
    profile.availability_notes = notes
    _audit(session, profile, "volunteer.notes", {}, actor=actor)


async def follow_member(
    session: AsyncSession, member: PartyMember, new_status: PartyMemberStatus
) -> None:
    """Carry a member's new status to their profile, audited as "system"; the caller commits.

    A withdrawn or rejected member withdraws the profile; a suspended member makes an active
    one inactive. Does nothing when the member has no profile.
    """
    for attempt in range(2):
        profile = await _fresh(session, VolunteerProfile.member_id == member.id)
        if profile is None:
            return
        old = profile.status
        if new_status in (PartyMemberStatus.WITHDRAWN, PartyMemberStatus.REJECTED):
            if old is V.WITHDRAWN:
                return
            to, values = V.WITHDRAWN, {"withdraw_code": None}
        elif new_status is PartyMemberStatus.SUSPENDED and old is V.ACTIVE:
            to, values = V.INACTIVE, {}
        else:
            return
        try:
            await _set_status(session, profile, old, status=to, **values)
        except Refused:
            if attempt:
                raise
            continue
        _audit(
            session,
            profile,
            "volunteer.status",
            {"from": old.value, "to": to.value},
            actor_name="system",
        )
        return


async def apply_volunteer(
    session: AsyncSession, member: PartyMember, part: dict, code: str
) -> None:
    """Create or refresh the member's profile from a queued join's volunteer part."""
    values = {
        "interests": [VolunteerInterest(i).value for i in part["interests"]],
        "preferred_contact": ContactMethod(part["preferred_contact"]),
        "consent_wording": VOLUNTEER_WORDING,
        "consent_at": datetime.fromisoformat(part["consent_at"]),
        "withdraw_code": code,
    }
    old = None
    for attempt in range(2):
        profile = await _fresh(session, VolunteerProfile.member_id == member.id)
        if profile is None:
            profile = VolunteerProfile(member_id=member.id, status=V.INTERESTED, **values)
            session.add(profile)
            await session.flush()
            break
        old = profile.status
        to = V.INTERESTED if old is V.WITHDRAWN else old
        try:
            await _set_status(session, profile, old, status=to, **values)
        except Refused:
            if attempt:
                raise
            continue
        break
    _audit(
        session,
        profile,
        "volunteer.interest",
        {"from": old.value if old else None, "to": profile.status.value},
    )


async def withdraw_volunteer(session: AsyncSession, profile: VolunteerProfile) -> None:
    """The volunteer's own withdrawal through their link; the link works once."""
    old = profile.status
    check_move(old, V.WITHDRAWN)
    await _set_status(session, profile, old, status=V.WITHDRAWN, withdraw_code=None)
    _audit(session, profile, "volunteer.withdraw", {"from": old.value, "to": V.WITHDRAWN.value})


async def withdraw_by_code(session: AsyncSession, code: str) -> None:
    """Withdraw the profile holding `code`; reads again once if an officer moved it."""
    for _ in range(2):
        profile = await _fresh(session, VolunteerProfile.withdraw_code == code)
        if profile is None:
            return
        try:
            await withdraw_volunteer(session, profile)
            return
        except Refused:
            continue


def _like(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped.lower()}%"


@dataclass(frozen=True)
class VolunteerFilters:
    q: str | None = None
    status: VolunteerStatus | None = None
    interest: VolunteerInterest | None = None
    county: uuid.UUID | None = None
    constituency: uuid.UUID | None = None
    ward: uuid.UUID | None = None

    def given(self) -> dict[str, str | bool]:
        """The filters in use, for the audit trail; `q` is recorded only as set."""
        found: dict[str, str | bool] = {}
        if self.q:
            found["q"] = True
        if self.status is not None:
            found["status"] = self.status.value
        if self.interest is not None:
            found["interest"] = self.interest.value
        for name in ("county", "constituency", "ward"):
            if getattr(self, name) is not None:
                found[name] = str(getattr(self, name))
        return found


def _query(filters: VolunteerFilters) -> Select:
    statement = (
        select(VolunteerProfile)
        .join(VolunteerProfile.member)
        .join(PartyMember.ward)
        .join(Ward.constituency)
        .options(
            contains_eager(VolunteerProfile.member)
            .contains_eager(PartyMember.ward)
            .contains_eager(Ward.constituency)
            .joinedload(Constituency.county)
        )
    )
    if filters.q and filters.q.strip():
        pattern = _like(filters.q.strip())
        matches = func.lower(PartyMember.full_name).like(pattern, escape="\\") | (
            PartyMember.phone.like(pattern, escape="\\")
        )
        local = filters.q.replace(" ", "")
        if local.startswith("0") and local[1:].isdigit():
            matches |= PartyMember.phone.like(_like("+254" + local[1:]), escape="\\")
        statement = statement.where(matches)
    if filters.status is not None:
        statement = statement.where(VolunteerProfile.status == filters.status)
    if filters.interest is not None:
        # The JSON list as text holds each value quoted, so "events" matches only that value.
        statement = statement.where(
            cast(VolunteerProfile.interests, String).like(
                _like(f'"{filters.interest.value}"'), escape="\\"
            )
        )
    if filters.county is not None:
        statement = statement.where(Constituency.county_id == filters.county)
    if filters.constituency is not None:
        statement = statement.where(Ward.constituency_id == filters.constituency)
    if filters.ward is not None:
        statement = statement.where(PartyMember.ward_id == filters.ward)
    return statement.order_by(VolunteerProfile.created_at.desc(), VolunteerProfile.id)


async def volunteers(
    session: AsyncSession, filters: VolunteerFilters, limit: int, offset: int
) -> tuple[int, list[VolunteerProfile]]:
    """One page of the volunteer register, newest first, and the count of all that match."""
    statement = _query(filters)
    total = await session.scalar(
        select(func.count()).select_from(
            statement.order_by(None).with_only_columns(VolunteerProfile.id).subquery()
        )
    )
    page = await session.scalars(statement.limit(limit).offset(offset))
    return total or 0, list(page.unique())


async def export_rows(session: AsyncSession, filters: VolunteerFilters) -> list[VolunteerProfile]:
    """Every volunteer matching the filters, newest first."""
    return list((await session.scalars(_query(filters))).unique())


async def get_volunteer(session: AsyncSession, volunteer_id: uuid.UUID) -> VolunteerProfile:
    """The profile with its member and places loaded; NotFound when missing."""
    profile = await session.scalar(
        _query(VolunteerFilters())
        .where(VolunteerProfile.id == volunteer_id)
        .execution_options(populate_existing=True)
    )
    if profile is None:
        raise NotFound("No such volunteer.")
    return profile
