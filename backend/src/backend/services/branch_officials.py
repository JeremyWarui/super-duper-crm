"""Branch officials as terms in office: who holds each office now, who is next, and who held it.

A term is current from `term_start` until `term_end`, inclusive. Appointing someone ends the
term it overlaps the day before the new one starts, so an office never has two holders at once.
"""

import uuid
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_or_refuse
from backend.models import (
    Branch,
    BranchOffice,
    BranchOfficial,
    County,
    FileArea,
    PartyMember,
    PartyMemberStatus,
    StoredFile,
    TermEnd,
    User,
)
from backend.schemas.content import OfficialAppoint, OfficialEnd
from backend.services.audit import record
from backend.services.errors import NotFound, Refused

ORDER = {office: i for i, office in enumerate(BranchOffice)}


def is_current(row: BranchOfficial, today: date) -> bool:
    return row.term_start <= today and (row.term_end is None or row.term_end >= today)


def label(row: BranchOfficial) -> str:
    return row.title if row.office is BranchOffice.OTHER and row.title else row.office.label


def _sorted(rows: list[BranchOfficial]) -> list[BranchOfficial]:
    return sorted(rows, key=lambda r: (ORDER[r.office], r.title, r.term_start))


async def current_by_branch(
    session: AsyncSession, branch_ids: list[uuid.UUID], today: date
) -> dict[uuid.UUID, list[BranchOfficial]]:
    """Each branch's officials in office today, in office order, leaving out any holder who is
    no longer an approved member."""
    if not branch_ids:
        return {}
    rows = await session.scalars(
        select(BranchOfficial)
        .outerjoin(PartyMember, PartyMember.id == BranchOfficial.member_id)
        .where(
            BranchOfficial.branch_id.in_(branch_ids),
            BranchOfficial.term_start <= today,
            or_(BranchOfficial.term_end.is_(None), BranchOfficial.term_end >= today),
            # A holder whose membership has lapsed is not named; a carried-over name has none.
            or_(
                BranchOfficial.member_id.is_(None), PartyMember.status == PartyMemberStatus.APPROVED
            ),
        )
    )
    found: dict[uuid.UUID, list[BranchOfficial]] = defaultdict(list)
    for row in rows:
        found[row.branch_id].append(row)
    return {branch_id: _sorted(found[branch_id]) for branch_id in found}


def public(rows: list[BranchOfficial]) -> list[dict]:
    """What the website shows of the officials in office: the office and the name."""
    return [{"office": r.office, "label": label(r), "name": r.holder_name} for r in rows]


async def branch_of(session: AsyncSession, county_id: uuid.UUID, *, create: bool) -> Branch | None:
    await get_or_refuse(session, County, county_id, "county")
    query = select(Branch).where(Branch.county_id == county_id)
    # Appointments to one branch run one at a time, so their date checks cannot race.
    branch = await session.scalar(query.with_for_update() if create else query)
    if branch is None and create:
        branch = Branch(county_id=county_id)
        session.add(branch)
        await session.flush()
    return branch


async def lapsed(session: AsyncSession, rows: list[BranchOfficial]) -> set[uuid.UUID]:
    """The terms whose holder is no longer an approved member."""
    ids = {r.member_id for r in rows if r.member_id is not None}
    if not ids:
        return set()
    approved = set(
        await session.scalars(
            select(PartyMember.id).where(
                PartyMember.id.in_(ids), PartyMember.status == PartyMemberStatus.APPROVED
            )
        )
    )
    return {r.id for r in rows if r.member_id is not None and r.member_id not in approved}


async def officials(session: AsyncSession, county_id: uuid.UUID, today: date) -> dict:
    """The county branch's terms: in office now, starting later, and ended; `lapsed` names the
    terms whose holder's membership has lapsed, which the website no longer shows."""
    branch = await branch_of(session, county_id, create=False)
    rows = (
        list(
            await session.scalars(
                select(BranchOfficial).where(BranchOfficial.branch_id == branch.id)
            )
        )
        if branch is not None
        else []
    )
    return {
        "lapsed": await lapsed(session, rows),
        "current": _sorted([r for r in rows if is_current(r, today)]),
        "upcoming": _sorted([r for r in rows if r.term_start > today]),
        "history": sorted(
            (r for r in rows if r.term_end is not None and r.term_end < today),
            key=lambda r: r.term_end,
            reverse=True,
        ),
    }


async def appoint(
    session: AsyncSession, county_id: uuid.UUID, payload: OfficialAppoint, *, actor: User
) -> BranchOfficial:
    """Give an approved member a term in an office; the holder it overlaps leaves the day before."""
    member = await session.get(PartyMember, payload.member)
    if member is None or not member.is_approved:
        raise Refused("Only an approved party member can hold a branch office.")
    if payload.minutes_file is not None:
        minutes = await session.get(StoredFile, payload.minutes_file)
        if minutes is None or minutes.area is not FileArea.MINUTES:
            raise Refused("Attach the minutes through the officials screen.")
    branch = await branch_of(session, county_id, create=True)
    replaced = []
    if payload.office is not BranchOffice.OTHER:
        same_office = list(
            await session.scalars(
                select(BranchOfficial)
                .where(
                    BranchOfficial.branch_id == branch.id, BranchOfficial.office == payload.office
                )
                .with_for_update()
            )
        )
        later = [r for r in same_office if r.term_start >= payload.term_start]
        if later:
            raise Refused(
                f"{payload.office.label} already has a term from {later[0].term_start:%d %b %Y}; "
                "end it before appointing someone from an earlier date."
            )
        day_before = payload.term_start - timedelta(days=1)
        for row in same_office:
            if row.term_end is None or row.term_end >= payload.term_start:
                row.term_end, row.end_reason = day_before, TermEnd.REPLACED
                replaced.append(row.id)
        await session.flush()
    official = BranchOfficial(
        branch_id=branch.id,
        member_id=member.id,
        office=payload.office,
        title=payload.title if payload.office is BranchOffice.OTHER else "",
        holder_name=member.full_name,
        term_start=payload.term_start,
        term_end=payload.term_end,
        start_reason=payload.start_reason,
        minutes_file_id=payload.minutes_file,
        note=payload.note,
        appointed_by_id=actor.id,
    )
    session.add(official)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise Refused(
            f"{payload.office.label} already has a holder; reload and try again."
        ) from None
    record(
        session,
        actor=actor,
        action="party.branch.official.appoint",
        subject_type="branch_official",
        subject_id=official.id,
        detail={
            "county": str(county_id),
            "office": payload.office.value,
            "member": str(member.id),
            "from": payload.term_start.isoformat(),
            "replaced": [str(i) for i in replaced],
        },
    )
    await session.commit()
    return official


async def end_term(
    session: AsyncSession, official_id: uuid.UUID, payload: OfficialEnd, *, actor: User
) -> BranchOfficial:
    """Close a term on a day; the office stands vacant from the next day."""
    row = await get_or_refuse(session, BranchOfficial, official_id, "term")
    if row.term_end is not None and row.term_end < payload.term_end:
        raise Refused("That term already ends sooner.")
    if payload.term_end < row.term_start:
        raise Refused("A term cannot end before it starts.")
    row.term_end, row.end_reason = payload.term_end, payload.end_reason
    record(
        session,
        actor=actor,
        action="party.branch.official.end",
        subject_type="branch_official",
        subject_id=row.id,
        detail={
            "office": row.office.value,
            "to": payload.term_end.isoformat(),
            "reason": payload.end_reason.value,
        },
    )
    await session.commit()
    return row


async def minutes_of(session: AsyncSession, official_id: uuid.UUID) -> StoredFile:
    row = await session.get(BranchOfficial, official_id)
    file = (
        await session.get(StoredFile, row.minutes_file_id) if row and row.minutes_file_id else None
    )
    if file is None:
        raise NotFound("No minutes are attached to that term.")
    return file
