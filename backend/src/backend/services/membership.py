"""The party register: which status moves are allowed, and the officer's move."""

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from backend.models import Constituency, PartyMember, PartyMemberStatus, User, Ward
from backend.services.audit import record
from backend.services.errors import NotFound, Refused

S = PartyMemberStatus

MOVES: dict[PartyMemberStatus, frozenset[PartyMemberStatus]] = {
    S.PENDING: frozenset({S.APPROVED, S.REJECTED, S.WITHDRAWN}),
    S.APPROVED: frozenset({S.SUSPENDED, S.WITHDRAWN}),
    S.SUSPENDED: frozenset({S.APPROVED, S.WITHDRAWN}),
    S.REJECTED: frozenset({S.PENDING}),
    S.WITHDRAWN: frozenset({S.PENDING}),
}


def new_withdraw_code() -> str:
    """The private code a self-registered member withdraws with."""
    return secrets.token_urlsafe(18)


def check_move(frm: PartyMemberStatus, to: PartyMemberStatus) -> None:
    """Refuse a move the table does not list."""
    if to not in MOVES[frm]:
        raise Refused(f"A {frm.label.lower()} member cannot be moved to {to.label.lower()}.")


async def move(
    session: AsyncSession,
    member: PartyMember,
    to: PartyMemberStatus,
    *,
    actor: User,
    reason: str | None = None,
) -> None:
    """An officer's status move, audited; the caller commits."""
    old = member.status
    if to is S.PENDING:
        raise Refused("Only the person re-applying puts a member back to pending.")
    check_move(old, to)
    member.status = to
    member.status_reason = reason
    member.decided_at = datetime.now(UTC)
    member.decided_by_id = actor.id
    record(
        session,
        actor=actor,
        action="member.status",
        subject_type="party_member",
        subject_id=member.id,
        detail={"from": old.value, "to": to.value},
    )


def withdraw(member: PartyMember) -> None:
    """The member's own withdrawal through their link; the link works once. The caller commits."""
    check_move(member.status, S.WITHDRAWN)
    member.status = S.WITHDRAWN
    member.status_reason = None
    member.decided_at = datetime.now(UTC)
    member.decided_by_id = None
    member.withdraw_code = None


@dataclass(frozen=True)
class MemberFilters:
    q: str | None = None
    status: PartyMemberStatus | None = None
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
        for name in ("county", "constituency", "ward"):
            if getattr(self, name) is not None:
                found[name] = str(getattr(self, name))
        return found


def _like(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped.lower()}%"


def _query(filters: MemberFilters) -> Select:
    statement = (
        select(PartyMember)
        .join(PartyMember.ward)
        .join(Ward.constituency)
        .options(
            contains_eager(PartyMember.ward)
            .contains_eager(Ward.constituency)
            .joinedload(Constituency.county)
        )
    )
    if filters.q and filters.q.strip():
        pattern = _like(filters.q.strip())
        statement = statement.where(
            func.lower(PartyMember.full_name).like(pattern, escape="\\")
            | PartyMember.phone.like(pattern, escape="\\")
        )
    if filters.status is not None:
        statement = statement.where(PartyMember.status == filters.status)
    if filters.county is not None:
        statement = statement.where(Constituency.county_id == filters.county)
    if filters.constituency is not None:
        statement = statement.where(Ward.constituency_id == filters.constituency)
    if filters.ward is not None:
        statement = statement.where(PartyMember.ward_id == filters.ward)
    return statement.order_by(PartyMember.created_at.desc(), PartyMember.id)


async def members(
    session: AsyncSession, filters: MemberFilters, limit: int, offset: int
) -> tuple[int, list[PartyMember]]:
    """One page of the register, newest first, and the count of all that match."""
    statement = _query(filters)
    total = await session.scalar(
        select(func.count()).select_from(
            statement.order_by(None).with_only_columns(PartyMember.id).subquery()
        )
    )
    page = await session.scalars(statement.limit(limit).offset(offset))
    return total or 0, list(page.unique())


async def export_rows(session: AsyncSession, filters: MemberFilters) -> list[PartyMember]:
    """Every member matching the filters, newest first."""
    return list((await session.scalars(_query(filters))).unique())


async def get_member(session: AsyncSession, member_id: uuid.UUID) -> PartyMember:
    """The member with places loaded; NotFound when missing."""
    member = await session.scalar(_query(MemberFilters()).where(PartyMember.id == member_id))
    if member is None:
        raise NotFound("No such member.")
    return member
