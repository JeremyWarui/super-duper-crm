"""The party register: allowed status moves, officer moves, and the public request inbox."""

import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager
from sqlalchemy.orm.attributes import set_committed_value

from backend.db.session import upsert
from backend.models import (
    Constituency,
    ContactMethod,
    PartyConsentChannel,
    PartyMember,
    PartyMemberStatus,
    PartyRequest,
    PartyRequestKind,
    PartySettings,
    Profession,
    User,
    VolunteerArea,
    Ward,
)
from backend.services import aspirants, volunteers
from backend.services.audit import record, record_if
from backend.services.consent import PARTY_WORDING
from backend.services.errors import NotFound, Refused, refuse_own_record

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


async def move(
    session: AsyncSession,
    member: PartyMember,
    to: PartyMemberStatus,
    *,
    actor: User,
    reason: str | None = None,
) -> None:
    """An officer's status move, audited; the caller commits."""
    refuse_own_record(actor, member.id)
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
    await aspirants.follow_member(session, member, to)


def request_join(
    session: AsyncSession,
    *,
    first_name: str,
    surname: str,
    phone: str,
    email: str,
    password_hash: str,
    ward_id: uuid.UUID,
    registration_centre_id: uuid.UUID,
    volunteer: dict | None = None,
) -> tuple[str, str | None]:
    """Queue a public application; returns its withdraw code and the volunteer one, if any.

    The caller commits and checks that the centre lies in the ward.

    Every application is this one insert, whatever the register holds, so neither the answer
    nor its timing shows whether the phone is registered.
    """
    code = new_withdraw_code()
    now = datetime.now(UTC).isoformat()
    payload = {
        "first_name": first_name,
        "surname": surname,
        "full_name": f"{first_name} {surname}"[:150],
        "phone": phone,
        "email": email,
        "password_hash": password_hash,
        "ward_id": str(ward_id),
        "registration_centre_id": str(registration_centre_id),
        "consent_wording": PARTY_WORDING[PartyConsentChannel.WEB_FORM],
        "consent_at": now,
    }
    volunteer_code = None
    if volunteer is not None:
        volunteer_code = new_withdraw_code()
        payload["volunteer"] = {
            "profession": Profession(volunteer["profession"]).value,
            "profession_other": volunteer.get("profession_other", ""),
            "areas": [VolunteerArea(a).value for a in volunteer["areas"]],
            "area_other": volunteer.get("area_other", ""),
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


# Statuses a member's own link can withdraw from.
WITHDRAWABLE = frozenset(old for old, targets in MOVES.items() if S.WITHDRAWN in targets)


def _uuid(value: str | None) -> uuid.UUID | None:
    return uuid.UUID(value) if value else None


async def _apply_join(session: AsyncSession, code: str, p: dict) -> None:
    """Add the applicant, or put a rejected or withdrawn member back to pending.

    Any other member is left as they are and the code withdraws nothing.
    """
    values = {
        "full_name": p["full_name"],
        "first_name": p.get("first_name"),
        "email": p["email"],
        "ward_id": uuid.UUID(p["ward_id"]),
        "registration_centre_id": _uuid(p.get("registration_centre_id")),
        "consent_channel": PartyConsentChannel.WEB_FORM,
        "consent_wording": p["consent_wording"],
        "consent_at": datetime.fromisoformat(p["consent_at"]),
        "withdraw_code": code,
    }
    found = select(PartyMember.id, PartyMember.status).where(PartyMember.phone == p["phone"])
    old = (await session.execute(found.with_for_update())).first()
    changed = await session.scalar(
        upsert(session, PartyMember)
        .values(id=uuid.uuid4(), phone=p["phone"], status=S.PENDING, **values)
        .on_conflict_do_update(
            index_elements=["phone"],
            set_={
                **values,
                "status": S.PENDING,
                "status_reason": None,
                "decided_at": None,
                "decided_by_id": None,
            },
            where=PartyMember.status.in_([S.REJECTED, S.WITHDRAWN]),
        )
        .returning(PartyMember.id)
    )
    member = (await session.execute(found)).one()
    await record_if(
        session,
        changed is not None and old is not None,
        actor_name="public",
        action="member.reapply",
        subject_type="party_member",
        subject_id=member.id,
        detail={"from": old.status.value if old else None, "to": S.PENDING.value},
    )
    if "volunteer" in p:
        await volunteers.apply_part(session, member.id, p, changed is not None)


async def _apply_withdraw(session: AsyncSession, code: str, p: dict) -> None:
    """Withdraw the member holding `code`, and their volunteer profile."""
    old = (
        await session.execute(
            select(PartyMember.id, PartyMember.status)
            .where(PartyMember.withdraw_code == code)
            .with_for_update()
        )
    ).first()
    changed = await session.execute(
        update(PartyMember)
        .where(PartyMember.withdraw_code == code, PartyMember.status.in_(WITHDRAWABLE))
        .values(
            status=S.WITHDRAWN,
            status_reason=None,
            decided_at=datetime.now(UTC),
            decided_by_id=None,
            withdraw_code=None,
        )
        .execution_options(synchronize_session=False)
    )
    withdrawn = changed.rowcount == 1
    await record_if(
        session,
        withdrawn,
        actor_name="public",
        action="member.withdraw",
        subject_type="party_member",
        subject_id=old.id if old else None,
        detail={"from": old.status.value if old else None, "to": S.WITHDRAWN.value},
    )
    await volunteers.follow_withdrawal(session, old.id if old else None, withdrawn)
    await aspirants.follow_withdrawal(session, old.id if old else None, withdrawn)


async def _apply_volunteer_withdraw(session: AsyncSession, code: str, p: dict) -> None:
    await volunteers.withdraw_by_code(session, code)


APPLY = {
    PartyRequestKind.JOIN: _apply_join,
    PartyRequestKind.WITHDRAW: _apply_withdraw,
    PartyRequestKind.VOLUNTEER_WITHDRAW: _apply_volunteer_withdraw,
}


async def process_requests(session: AsyncSession, *, limit: int = 100) -> int:
    """Apply queued public requests oldest first, one at a time, each in its own transaction.

    A request of each kind runs the same statements whatever the register holds, so how long
    the work takes never depends on it. Processors take turns on the party settings row, so a
    withdrawal is never applied before the join it belongs to. A request that cannot be applied
    is logged by id and dropped. Returns how many requests were taken.
    """
    await session.commit()
    taken = 0
    while taken < limit:
        await session.execute(
            select(PartySettings.id).where(PartySettings.id == 1).with_for_update()
        )
        oldest = (
            await session.execute(
                select(PartyRequest.id, PartyRequest.kind, PartyRequest.code, PartyRequest.payload)
                .order_by(PartyRequest.created_at, PartyRequest.id)
                .limit(1)
            )
        ).first()
        if oldest is None:
            await session.commit()
            break
        claimed = await session.execute(delete(PartyRequest).where(PartyRequest.id == oldest.id))
        if claimed.rowcount != 1:
            await session.commit()
            continue
        try:
            async with session.begin_nested():
                await APPLY[oldest.kind](session, oldest.code, oldest.payload)
        except Exception:
            log.exception("Party request %s could not be applied and was dropped.", oldest.id)
        await session.commit()
        taken += 1
    return taken


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
