"""The party register: which status moves are allowed, and the officer's move."""

import secrets
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import PartyMember, PartyMemberStatus, User
from backend.services.audit import record
from backend.services.errors import Refused

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
