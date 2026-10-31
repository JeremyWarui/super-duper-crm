"""The party register: allowed status moves, officer moves, and the public request inbox."""

import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager
from sqlalchemy.orm.attributes import set_committed_value

from backend.models import (
    Constituency,
    ContactMethod,
    PartyConsentChannel,
    PartyMember,
    PartyMemberStatus,
    PartyRequest,
    PartyRequestKind,
    User,
    VolunteerInterest,
    Ward,
)
from backend.services import volunteers
from backend.services.audit import record
from backend.services.consent import PARTY_WORDING
from backend.services.errors import NotFound, Refused

log = logging.getLogger(__name__)

S = PartyMemberStatus

MOVES: dict[PartyMemberStatus, frozenset[PartyMemberStatus]] = {
    S.PENDING: frozenset({S.APPROVED, S.REJECTED, S.WITHDRAWN}),
    S.APPROVED: frozenset({S.SUSPENDED, S.WITHDRAWN}),
    S.SUSPENDED: frozenset({S.APPROVED, S.WITHDRAWN}),
    S.REJECTED: frozenset({S.PENDING, S.WITHDRAWN}),
    S.WITHDRAWN: frozenset({S.PENDING}),
}


def new_withdraw_code() -> str:
    """The private code a self-registered member withdraws with."""
    return secrets.token_urlsafe(18)


def check_move(frm: PartyMemberStatus, to: PartyMemberStatus) -> None:
    """Refuse a move the table does not list."""
    if to not in MOVES[frm]:
        raise Refused(f"A {frm.label.lower()} member cannot be moved to {to.label.lower()}.")


async def _set_status(
    session: AsyncSession, member: PartyMember, old: PartyMemberStatus, **values
) -> None:
    """Write the move only if the row still has the status it was checked against."""
    changed = await session.execute(
        update(PartyMember)
        .where(PartyMember.id == member.id, PartyMember.status == old)
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        raise Refused("This member's status changed meanwhile; reload and try again.")
    for name, value in values.items():
        set_committed_value(member, name, value)


async def reapply(
    session: AsyncSession, member: PartyMember, old: PartyMemberStatus, **values
) -> bool:
    """Put a rejected or withdrawn member back to pending, audited with the status it left.

    False when the row no longer has status `old`, because an officer moved it meanwhile.
    """
    if old not in (S.REJECTED, S.WITHDRAWN):
        return False
    changed = await session.execute(
        update(PartyMember)
        .where(PartyMember.id == member.id, PartyMember.status == old)
        .values(status=S.PENDING, status_reason=None, decided_at=None, decided_by_id=None, **values)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        return False
    record(
        session,
        actor=None,
        actor_name="public",
        action="member.reapply",
        subject_type="party_member",
        subject_id=member.id,
        detail={"from": old.value, "to": S.PENDING.value},
    )
    return True


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
    cleared = {"withdraw_code": None} if to is S.WITHDRAWN else {}
    await _set_status(
        session,
        member,
        old,
        status=to,
        status_reason=reason,
        decided_at=datetime.now(UTC),
        decided_by_id=actor.id,
        **cleared,
    )
    record(
        session,
        actor=actor,
        action="member.status",
        subject_type="party_member",
        subject_id=member.id,
        detail={"from": old.value, "to": to.value},
    )
    await volunteers.follow_member(session, member, to)


async def withdraw(session: AsyncSession, member: PartyMember) -> None:
    """The member's own withdrawal through their link; the link works once. The caller commits."""
    old = member.status
    check_move(old, S.WITHDRAWN)
    await _set_status(
        session,
        member,
        old,
        status=S.WITHDRAWN,
        status_reason=None,
        decided_at=datetime.now(UTC),
        decided_by_id=None,
        withdraw_code=None,
    )
    record(
        session,
        actor=None,
        actor_name="public",
        action="member.withdraw",
        subject_type="party_member",
        subject_id=member.id,
        detail={"from": old.value, "to": S.WITHDRAWN.value},
    )
    await volunteers.follow_member(session, member, S.WITHDRAWN)


def request_join(
    session: AsyncSession,
    *,
    full_name: str,
    phone: str,
    email: str | None,
    ward_id: uuid.UUID,
    volunteer: dict | None = None,
) -> tuple[str, str | None]:
    """Queue a public application; returns its withdraw code and the volunteer one, if any.

    The caller commits.

    Every application is this one insert, whatever the register holds, so neither the answer
    nor its timing shows whether the phone is registered.
    """
    code = new_withdraw_code()
    now = datetime.now(UTC).isoformat()
    payload = {
        "full_name": full_name,
        "phone": phone,
        "email": email,
        "ward_id": str(ward_id),
        "consent_wording": PARTY_WORDING[PartyConsentChannel.WEB_FORM],
        "consent_at": now,
    }
    volunteer_code = None
    if volunteer is not None:
        volunteer_code = new_withdraw_code()
        payload["volunteer"] = {
            "interests": [VolunteerInterest(i).value for i in volunteer["interests"]],
            "preferred_contact": ContactMethod(volunteer["preferred_contact"]).value,
            "consent_at": now,
            "code": volunteer_code,
        }
    session.add(PartyRequest(kind=PartyRequestKind.JOIN, code=code, payload=payload))
    return code, volunteer_code


def request_withdraw(session: AsyncSession, code: str) -> None:
    """Queue a public withdrawal by code; the caller commits."""
    session.add(PartyRequest(kind=PartyRequestKind.WITHDRAW, code=code, payload={}))


def request_volunteer_withdraw(session: AsyncSession, code: str) -> None:
    """Queue a public volunteer withdrawal by code; the caller commits."""
    session.add(PartyRequest(kind=PartyRequestKind.VOLUNTEER_WITHDRAW, code=code, payload={}))


async def _fresh(session: AsyncSession, where) -> PartyMember | None:
    """The member matching `where`, read from the database rather than the session."""
    return await session.scalar(
        select(PartyMember).where(where).execution_options(populate_existing=True)
    )


async def _apply_join(session: AsyncSession, request: PartyRequest) -> None:
    p = request.payload
    values = {
        "full_name": p["full_name"],
        "email": p["email"],
        "ward_id": uuid.UUID(p["ward_id"]),
        "consent_channel": PartyConsentChannel.WEB_FORM,
        "consent_wording": p["consent_wording"],
        "consent_at": datetime.fromisoformat(p["consent_at"]),
        "withdraw_code": request.code,
    }
    for _ in range(2):
        member = await _fresh(session, PartyMember.phone == p["phone"])
        if member is None:
            member = PartyMember(phone=p["phone"], status=S.PENDING, **values)
            session.add(member)
            await session.flush()
            break
        if member.status not in (S.REJECTED, S.WITHDRAWN):
            break  # already an application or membership; the code withdraws nothing
        if await reapply(session, member, member.status, **values):
            break
    else:
        return
    if "volunteer" in p:
        await volunteers.apply_volunteer(session, member, p["volunteer"], p["volunteer"]["code"])


async def _apply_withdraw(session: AsyncSession, code: str) -> None:
    for _ in range(2):
        member = await _fresh(session, PartyMember.withdraw_code == code)
        if member is None:
            return
        try:
            await withdraw(session, member)
            return
        except Refused:
            continue  # an officer moved them between the read and the write; read again


async def process_requests(session: AsyncSession, *, limit: int = 100) -> int:
    """Apply queued public requests in order, each once and in its own transaction.

    A request that cannot be applied is logged by id and dropped, so it never blocks the queue.
    Returns how many requests were taken.
    """
    queued = (
        await session.scalars(
            select(PartyRequest).order_by(PartyRequest.created_at, PartyRequest.id).limit(limit)
        )
    ).all()
    await session.commit()
    applied = 0
    for request in queued:
        claimed = await session.execute(delete(PartyRequest).where(PartyRequest.id == request.id))
        if claimed.rowcount != 1:
            await session.commit()
            continue  # another processor took it
        try:
            async with session.begin_nested():
                if request.kind is PartyRequestKind.JOIN:
                    await _apply_join(session, request)
                elif request.kind is PartyRequestKind.WITHDRAW:
                    await _apply_withdraw(session, request.code)
                else:
                    await volunteers.withdraw_by_code(session, request.code)
        except (IntegrityError, Refused):
            pass  # the same phone was added by a concurrent processor, or an officer moved it
        except Exception:
            log.exception("Party request %s could not be applied and was dropped.", request.id)
        await session.commit()
        applied += 1
    return applied


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
        matches = func.lower(PartyMember.full_name).like(pattern, escape="\\") | (
            PartyMember.phone.like(pattern, escape="\\")
        )
        local = filters.q.replace(" ", "")
        if local.startswith("0") and local[1:].isdigit():
            # Phones are stored as +254...; a number typed as 07... finds them too.
            matches |= PartyMember.phone.like(_like("+254" + local[1:]), escape="\\")
        statement = statement.where(matches)
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
