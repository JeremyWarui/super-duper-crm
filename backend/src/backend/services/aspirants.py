"""Nominations: the move table, officer moves, and aspirants following their member."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Boolean, Select, Uuid, bindparam, func, literal, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    Aspirant,
    AspirantStatus,
    PartyMember,
    PartyMemberStatus,
    Seat,
    User,
    Ward,
)
from backend.services.audit import record, record_if
from backend.services.campaigns import AREA_FIELD, AREA_MODEL
from backend.services.errors import NotFound, Refused
from backend.services.sms import normalise_phone

A = AspirantStatus
LIVE = frozenset({A.DRAFT, A.SUBMITTED, A.APPROVED, A.SUSPENDED})

MOVES: dict[AspirantStatus, frozenset[AspirantStatus]] = {
    A.DRAFT: frozenset({A.SUBMITTED, A.WITHDRAWN}),
    A.SUBMITTED: frozenset({A.APPROVED, A.REJECTED, A.WITHDRAWN}),
    A.APPROVED: frozenset({A.SUSPENDED, A.WITHDRAWN}),
    A.SUSPENDED: frozenset({A.APPROVED, A.WITHDRAWN}),
    A.REJECTED: frozenset(),
    A.WITHDRAWN: frozenset(),
}
NEEDS_REASON = frozenset({A.REJECTED, A.SUSPENDED})
CANDIDATE_LIMIT = 20

READ_OPTIONS = (
    selectinload(Aspirant.member).selectinload(PartyMember.ward),
    selectinload(Aspirant.county),
    selectinload(Aspirant.constituency),
    selectinload(Aspirant.ward),
)


async def _approved_member(session: AsyncSession, member_id: uuid.UUID) -> PartyMember:
    """The member, locked against a concurrent status move; refused unless approved."""
    member = await session.scalar(
        select(PartyMember).where(PartyMember.id == member_id).with_for_update()
    )
    if member is None:
        raise NotFound("No such member.")
    await session.refresh(member, ["status"])
    if member.status is not PartyMemberStatus.APPROVED:
        raise Refused("Only an approved party member can be an approved aspirant.")
    return member


async def nominate(
    session: AsyncSession,
    *,
    member_id: uuid.UUID,
    seat: Seat,
    county: uuid.UUID | None,
    constituency: uuid.UUID | None,
    ward: uuid.UUID | None,
    actor: User,
) -> Aspirant:
    """A draft nomination for an approved member with no live one; the caller commits."""
    await _approved_member(session, member_id)
    area_field = AREA_FIELD[seat.office_level]
    areas = {"county": county, "constituency": constituency, "ward": ward}
    area_id = areas[area_field]
    if area_id is None or any(v is not None for k, v in areas.items() if k != area_field):
        raise Refused(f"A {seat.label} nomination names its {area_field} and nothing else.")
    if await session.get(AREA_MODEL[seat.office_level], area_id) is None:
        raise Refused(f"No such {area_field}.")
    live = await session.scalar(
        select(Aspirant.id).where(Aspirant.member_id == member_id, Aspirant.status.in_(LIVE))
    )
    if live is not None:
        raise Refused("That member already has a live nomination.")
    aspirant = Aspirant(
        member_id=member_id, seat=seat, created_by_id=actor.id, **{f"{area_field}_id": area_id}
    )
    session.add(aspirant)
    await session.flush()
    record(
        session,
        actor=actor,
        action="aspirant.create",
        subject_type="aspirant",
        subject_id=aspirant.id,
        detail={"seat": seat.value},
    )
    return aspirant


async def move(
    session: AsyncSession,
    aspirant: Aspirant,
    to: AspirantStatus,
    *,
    actor: User,
    reason: str | None = None,
) -> None:
    """An officer's move on a nomination, audited; the caller commits."""
    old = aspirant.status
    if to not in MOVES[old]:
        raise Refused(f"A {old.label.lower()} nomination cannot be moved to {to.label.lower()}.")
    if to in NEEDS_REASON and not (reason and reason.strip()):
        raise Refused(f"Moving a nomination to {to.label.lower()} needs a reason.")
    if to is A.APPROVED:
        await _approved_member(session, aspirant.member_id)
    values = {
        "status": to,
        "status_reason": reason,
        "decided_at": datetime.now(UTC),
        "decided_by_id": actor.id,
    }
    changed = await session.execute(
        update(Aspirant)
        .where(Aspirant.id == aspirant.id, Aspirant.status == old)
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        raise Refused("This nomination changed meanwhile; reload and try again.")
    record(
        session,
        actor=actor,
        action="aspirant.status",
        subject_type="aspirant",
        subject_id=aspirant.id,
        detail={"from": old.value, "to": to.value},
    )


async def follow_member(
    session: AsyncSession, member: PartyMember, new_status: PartyMemberStatus
) -> None:
    """Carry an officer's member move to the member's live nomination, audited as "system"."""
    if new_status is PartyMemberStatus.SUSPENDED:
        frm, to = frozenset({A.APPROVED}), A.SUSPENDED
    elif new_status in (PartyMemberStatus.WITHDRAWN, PartyMemberStatus.REJECTED):
        frm, to = LIVE, A.WITHDRAWN
    else:
        return
    old = (
        await session.execute(
            select(Aspirant.id, Aspirant.status)
            .where(Aspirant.member_id == member.id, Aspirant.status.in_(frm))
            .with_for_update()
        )
    ).first()
    if old is None:
        return
    await session.execute(
        update(Aspirant)
        .where(Aspirant.id == old.id, Aspirant.status == old.status)
        .values(status=to, decided_at=datetime.now(UTC), decided_by_id=None)
        .execution_options(synchronize_session=False)
    )
    await record_if(
        session,
        True,
        actor_name="system",
        action="aspirant.status",
        subject_type="aspirant",
        subject_id=old.id,
        detail={"from": old.status.value, "to": to.value},
    )


async def follow_withdrawal(
    session: AsyncSession, member_id: uuid.UUID | None, withdrawn: bool
) -> None:
    """Withdraw the live nomination of a member the public link just withdrew.

    Runs the same statements whatever the register holds; audited as "system".
    """
    where = (
        Aspirant.member_id == bindparam("member_id", member_id, type_=Uuid),
        Aspirant.status.in_(LIVE),
    )
    old = (
        await session.execute(select(Aspirant.id, Aspirant.status).where(*where).with_for_update())
    ).first()
    changed = await session.execute(
        update(Aspirant)
        .where(*where, literal(withdrawn, Boolean))
        .values(status=A.WITHDRAWN, decided_at=datetime.now(UTC), decided_by_id=None)
        .execution_options(synchronize_session=False)
    )
    await record_if(
        session,
        changed.rowcount == 1,
        actor_name="system",
        action="aspirant.status",
        subject_type="aspirant",
        subject_id=old.id if old else None,
        detail={"from": old.status.value if old else None, "to": A.WITHDRAWN.value},
    )


@dataclass(frozen=True)
class AspirantFilters:
    status: AspirantStatus | None = None
    seat: Seat | None = None
    county: uuid.UUID | None = None
    constituency: uuid.UUID | None = None
    ward: uuid.UUID | None = None


def _query(filters: AspirantFilters) -> Select:
    statement = select(Aspirant).options(*READ_OPTIONS)
    if filters.status is not None:
        statement = statement.where(Aspirant.status == filters.status)
    if filters.seat is not None:
        statement = statement.where(Aspirant.seat == filters.seat)
    for name in ("county", "constituency", "ward"):
        if getattr(filters, name) is not None:
            statement = statement.where(getattr(Aspirant, f"{name}_id") == getattr(filters, name))
    return statement


async def aspirants(
    session: AsyncSession, filters: AspirantFilters, limit: int, offset: int
) -> tuple[int, list[Aspirant]]:
    """A page of nominations, newest first, and the total that match."""
    statement = _query(filters)
    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    rows = await session.scalars(
        statement.order_by(Aspirant.created_at.desc(), Aspirant.id).limit(limit).offset(offset)
    )
    return total or 0, list(rows.all())


async def get_aspirant(session: AsyncSession, aspirant_id: uuid.UUID) -> Aspirant:
    """The nomination with its member and area loaded; NotFound when missing."""
    aspirant = await session.scalar(
        _query(AspirantFilters())
        .where(Aspirant.id == aspirant_id)
        .execution_options(populate_existing=True)
    )
    if aspirant is None:
        raise NotFound("No such aspirant.")
    return aspirant


async def candidates(session: AsyncSession, q: str) -> list[PartyMember]:
    """Approved members with no live nomination, by name or by their exact full phone.

    Never matches part of a phone, so a phone cannot be found digit by digit.
    """
    text = q.strip()
    phone = normalise_phone(text) if any(c.isdigit() for c in text) else None
    if phone:
        match = PartyMember.phone == phone
    elif len(text) >= 2:
        escaped = text.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        match = func.lower(PartyMember.full_name).like(f"%{escaped}%", escape="\\")
    else:
        return []
    nominated = select(Aspirant.member_id).where(Aspirant.status.in_(LIVE))
    rows = await session.scalars(
        select(PartyMember)
        .options(selectinload(PartyMember.ward).selectinload(Ward.constituency))
        .where(
            match,
            PartyMember.status == PartyMemberStatus.APPROVED,
            PartyMember.id.not_in(nominated),
        )
        .order_by(PartyMember.full_name, PartyMember.id)
        .limit(CANDIDATE_LIMIT)
    )
    return list(rows.all())
