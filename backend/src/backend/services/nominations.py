"""Members applying to vie: the timetable the party publishes, a member's own application in an
open window, its documents and fee, and its submission for vetting.

The Nominations Officer drafts a window; the Party Super Admin, who is someone else, publishes it.
A member's application is a draft aspirant until the member submits it with the declaration
and, where the seat has a fee, after the officer marks the fee paid. Vetting is the officer's
existing status moves (`services/aspirants.py`); nothing is approved without them.
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.session import get_or_refuse, move_row
from backend.models import (
    Aspirant,
    AspirantDocument,
    AspirantStatus,
    Constituency,
    NominationSeat,
    NominationWindow,
    OfficeLevel,
    PartyMember,
    Seat,
    StoredFile,
    User,
    Ward,
)
from backend.services.aspirants import LIVE
from backend.services.audit import record
from backend.services.errors import NotFound, Refused, refuse_own_record

DRAFT, PUBLISHED = "draft", "published"

OWN_LIVE_NOMINATION = "You already have a live nomination."


def _check_dates(opens_on: date, closes_on: date) -> None:
    if closes_on < opens_on:
        raise Refused("Applications cannot close before they open.")


def _seats(window: NominationWindow, seats: list[tuple[Seat, int]]) -> None:
    if not seats:
        raise Refused("Open at least one seat.")
    if len({seat for seat, _ in seats}) != len(seats):
        raise Refused("Each seat is listed once.")
    window.seats = [NominationSeat(seat=seat, fee_kes=fee) for seat, fee in seats]


async def window(session: AsyncSession, window_id: uuid.UUID) -> NominationWindow:
    found = await session.scalar(
        select(NominationWindow)
        .where(NominationWindow.id == window_id)
        .options(selectinload(NominationWindow.seats))
    )
    if found is None:
        raise NotFound("No such timetable.")
    return found


async def windows(session: AsyncSession) -> list[NominationWindow]:
    return list(
        await session.scalars(
            select(NominationWindow)
            .options(selectinload(NominationWindow.seats))
            .order_by(NominationWindow.opens_on.desc())
        )
    )


async def draft(
    session: AsyncSession,
    *,
    title: str,
    opens_on: date,
    closes_on: date,
    requirements: str,
    seats: list[tuple[Seat, int]],
    actor: User,
) -> NominationWindow:
    _check_dates(opens_on, closes_on)
    row = NominationWindow(
        title=title,
        opens_on=opens_on,
        closes_on=closes_on,
        requirements=requirements,
        drafted_by_id=actor.id,
    )
    _seats(row, seats)
    session.add(row)
    await session.flush()
    record(
        session,
        actor=actor,
        action="nominations.window.draft",
        subject_type="nomination_window",
        subject_id=row.id,
    )
    await session.commit()
    return await window(session, row.id)


async def revise(
    session: AsyncSession,
    row: NominationWindow,
    *,
    title: str,
    opens_on: date,
    closes_on: date,
    requirements: str,
    seats: list[tuple[Seat, int]],
    actor: User,
) -> NominationWindow:
    """Change a draft; a published timetable is fixed. Whoever changes it becomes its drafter."""
    _check_dates(opens_on, closes_on)
    # Claims the row before the content changes, so a publish running alongside waits or fails.
    await move_row(
        session,
        row,
        "A published timetable cannot be changed.",
        NominationWindow.status == DRAFT,
        drafted_by_id=actor.id,
    )
    row.title, row.opens_on, row.closes_on, row.requirements = (
        title,
        opens_on,
        closes_on,
        requirements,
    )
    row.seats.clear()
    await session.flush()
    _seats(row, seats)
    record(
        session,
        actor=actor,
        action="nominations.window.revise",
        subject_type="nomination_window",
        subject_id=row.id,
    )
    await session.commit()
    return await window(session, row.id)


async def publish(
    session: AsyncSession, row: NominationWindow, *, actor: User, today: date
) -> NominationWindow:
    """The Party Super Admin publishes a draft someone else wrote; the dates may not overlap
    another published timetable."""
    if not actor.is_superuser:
        raise Refused("Only the Party Super Admin publishes a timetable.")
    if row.drafted_by_id == actor.id:
        raise Refused("Someone other than whoever drafted the timetable publishes it.")
    if row.status != DRAFT:
        raise Refused("That timetable is already published.")
    if row.closes_on < today:
        raise Refused("That timetable has already closed; change its dates first.")
    clash = await session.scalar(
        select(NominationWindow.title).where(
            NominationWindow.status == PUBLISHED,
            NominationWindow.opens_on <= row.closes_on,
            NominationWindow.closes_on >= row.opens_on,
        )
    )
    if clash is not None:
        raise Refused(f"Those dates overlap the published timetable “{clash}”.")
    await move_row(
        session,
        row,
        "That timetable changed meanwhile; reload and try again.",
        NominationWindow.status == DRAFT,
        NominationWindow.drafted_by_id != actor.id,
        status=PUBLISHED,
        published_by_id=actor.id,
        published_at=datetime.now(UTC),
    )
    record(
        session,
        actor=actor,
        action="nominations.window.publish",
        subject_type="nomination_window",
        subject_id=row.id,
    )
    await session.commit()
    await session.refresh(row)
    return await window(session, row.id)


async def current(session: AsyncSession, today: date) -> NominationWindow | None:
    """The published timetable that is open today, or the next one to open."""
    return await session.scalar(
        select(NominationWindow)
        .where(NominationWindow.status == PUBLISHED, NominationWindow.closes_on >= today)
        .options(selectinload(NominationWindow.seats))
        .order_by(NominationWindow.opens_on)
        .limit(1)
    )


def is_open(row: NominationWindow | None, today: date) -> bool:
    return row is not None and row.opens_on <= today <= row.closes_on


async def member_area(session: AsyncSession, member: PartyMember, seat: Seat) -> dict:
    """The area a member vies in for a seat: their own ward, its constituency or its county."""
    if member.ward_id is None:
        raise Refused("Your membership has no ward; ask the party office to add it first.")
    ward = await session.get(Ward, member.ward_id)
    level = seat.office_level
    if level is OfficeLevel.WARD:
        return {"ward_id": ward.id}
    if level is OfficeLevel.CONSTITUENCY:
        return {"constituency_id": ward.constituency_id}
    constituency = await session.get(Constituency, ward.constituency_id)
    return {"county_id": constituency.county_id}


async def mine(session: AsyncSession, member: PartyMember) -> Aspirant | None:
    """The member's live nomination, however it was made."""
    return await session.scalar(
        select(Aspirant)
        .where(Aspirant.member_id == member.id, Aspirant.status.in_(LIVE))
        .options(
            selectinload(Aspirant.documents),
            selectinload(Aspirant.window),
            selectinload(Aspirant.ward),
            selectinload(Aspirant.constituency),
            selectinload(Aspirant.county),
        )
    )


async def apply(
    session: AsyncSession, member: PartyMember, seat: Seat, *, actor: User, today: date
) -> Aspirant:
    """Start an approved member's application for a seat open in today's window."""
    if not member.is_approved:
        raise Refused("Only an approved party member can apply to vie.")
    row = await current(session, today)
    if not is_open(row, today):
        raise Refused("Applications are not open now.")
    offered = next((s for s in row.seats if s.seat is seat), None)
    if offered is None:
        raise Refused(f"{seat.label} is not open in this timetable.")
    if await mine(session, member) is not None:
        raise Refused(OWN_LIVE_NOMINATION)
    aspirant = Aspirant(
        member_id=member.id,
        seat=seat,
        window_id=row.id,
        fee_kes=offered.fee_kes,
        created_by_id=actor.id,
        **await member_area(session, member, seat),
    )
    session.add(aspirant)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise Refused(OWN_LIVE_NOMINATION) from None
    record(
        session,
        actor=actor,
        action="nominations.apply",
        subject_type="aspirant",
        subject_id=aspirant.id,
        detail={"seat": seat.value},
    )
    await session.commit()
    return aspirant


def own_draft(aspirant: Aspirant | None) -> Aspirant:
    if aspirant is None or aspirant.window_id is None:
        raise NotFound("You have no application.")
    if aspirant.status is not AspirantStatus.DRAFT:
        raise Refused("Your application has been submitted and can no longer change.")
    return aspirant


async def attach(
    session: AsyncSession, aspirant: Aspirant | None, file: StoredFile, label: str, *, actor: User
) -> AspirantDocument:
    aspirant = own_draft(aspirant)
    document = AspirantDocument(aspirant_id=aspirant.id, label=label, file_id=file.id)
    session.add(document)
    await session.flush()
    record(
        session,
        actor=actor,
        action="nominations.document",
        subject_type="aspirant",
        subject_id=aspirant.id,
        detail={"label": label},
    )
    await session.commit()
    return document


async def detach(session: AsyncSession, aspirant: Aspirant | None, document_id: uuid.UUID) -> None:
    aspirant = own_draft(aspirant)
    document = await get_or_refuse(
        session, AspirantDocument, document_id, "document", match={"aspirant_id": aspirant.id}
    )
    await session.delete(document)
    await session.commit()


async def submit(
    session: AsyncSession, aspirant: Aspirant | None, *, actor: User, today: date
) -> Aspirant:
    """Send the application for vetting: the window must still be open and any fee paid."""
    aspirant = own_draft(aspirant)
    row = await session.get(NominationWindow, aspirant.window_id)
    if not is_open(row, today):
        raise Refused("Applications have closed.")
    if aspirant.fee_kes > 0 and aspirant.fee_paid_at is None:
        raise Refused(
            f"The KES {aspirant.fee_kes:,} nomination fee is not marked paid yet. Pay it as the "
            "party's instructions say; the nominations officer marks it paid."
        )
    await move_row(
        session,
        aspirant,
        "Your application changed meanwhile; reload and try again.",
        Aspirant.status == AspirantStatus.DRAFT,
        status=AspirantStatus.SUBMITTED,
        declared_at=datetime.now(UTC),
    )
    record(
        session,
        actor=actor,
        action="nominations.submit",
        subject_type="aspirant",
        subject_id=aspirant.id,
    )
    await session.commit()
    await session.refresh(aspirant)
    return aspirant


async def withdraw(session: AsyncSession, aspirant: Aspirant | None, *, actor: User) -> None:
    """The member takes back an application not yet decided."""
    if aspirant is None or aspirant.window_id is None:
        raise NotFound("You have no application.")
    await move_row(
        session,
        aspirant,
        "Only an application not yet decided can be withdrawn.",
        Aspirant.status.in_((AspirantStatus.DRAFT, AspirantStatus.SUBMITTED)),
        status=AspirantStatus.WITHDRAWN,
        decided_at=datetime.now(UTC),
    )
    record(
        session,
        actor=actor,
        action="nominations.withdraw",
        subject_type="aspirant",
        subject_id=aspirant.id,
    )
    await session.commit()


def require_fee_open(
    aspirant: Aspirant,
    *,
    paid: str = "The fee is already marked paid.",
    not_draft: str = "Only a draft application's fee is marked paid.",
) -> None:
    """Refused unless the application has a fee, still unpaid, and is a draft."""
    if aspirant.fee_kes <= 0:
        raise Refused("This application has no fee to pay.")
    if aspirant.fee_paid_at is not None:
        raise Refused(paid)
    if aspirant.status is not AspirantStatus.DRAFT:
        raise Refused(not_draft)


def stamp_fee(
    aspirant: Aspirant, reference: str, marked_by_id: uuid.UUID | None, at: datetime
) -> None:
    """Record the fee paid at `at` under `reference`."""
    aspirant.fee_paid_at = at
    aspirant.fee_reference = reference
    aspirant.fee_marked_by_id = marked_by_id


async def mark_fee_paid(
    session: AsyncSession, aspirant: Aspirant, reference: str, *, actor: User
) -> Aspirant:
    """The officer records the nomination fee paid, under its M-Pesa or bank reference."""
    refuse_own_record(actor, aspirant.member_id)
    require_fee_open(aspirant)
    stamp_fee(aspirant, reference, actor.id, datetime.now(UTC))
    record(
        session,
        actor=actor,
        action="nominations.fee_paid",
        subject_type="aspirant",
        subject_id=aspirant.id,
        detail={"reference": reference, "amount": aspirant.fee_kes},
    )
    await session.commit()
    return aspirant


async def document(
    session: AsyncSession, aspirant_id: uuid.UUID, document_id: uuid.UUID
) -> StoredFile:
    row = await get_or_refuse(
        session, AspirantDocument, document_id, "document", match={"aspirant_id": aspirant_id}
    )
    return await session.get(StoredFile, row.file_id)
