"""The strategy read: what the numbers say to do next.

Derived from targets, events and mobilizers on every request. Nothing here is
stored, so it can never disagree with the rows it is built from.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import Event, Mobilizer, Target

# Enough events that more of them are better spent somewhere else.
WELL_WORKED = 4


@dataclass
class Unit:
    unit: str
    needed: int
    committed: int
    gap: int
    progress: float
    events: int
    has_mobilizer: bool
    share: float = 0.0


@dataclass
class Note:
    tone: str
    title: str
    text: str


@dataclass
class Strategy:
    win_number: int
    committed: int
    progress_pct: float
    total_registered: int
    total_cast: int
    units: list[Unit] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)


async def read_strategy(
    session: AsyncSession,
    *,
    campaign_ids: frozenset[uuid.UUID] | None = None,
    campaign_id: uuid.UUID | None = None,
    ward_id: uuid.UUID | None = None,
) -> Strategy:
    """Roll the campaign's targets up, then say what stands out.

    `campaign_ids` limits it to the campaigns the caller may see, `campaign_id`
    to the one they asked for, and `ward_id` to a mobilizer's own ward.
    """
    statement = select(Target).options(
        selectinload(Target.ward), selectinload(Target.registration_centre)
    )
    if campaign_id is not None:
        statement = statement.where(Target.campaign_id == campaign_id)
    if campaign_ids is not None:
        statement = statement.where(Target.campaign_id.in_(campaign_ids))
    if ward_id is not None:
        statement = statement.where(Target.ward_id == ward_id)
    targets = list((await session.execute(statement)).scalars().all())

    events = await _events_per_unit(session, targets)
    staffed = await _staffed_units(session, targets)

    units: list[Unit] = []
    win_number = committed = total_registered = total_cast = 0
    for target in targets:
        needed = target.votes_needed or 0
        has = target.votes_committed or 0
        win_number += needed
        committed += has
        registered = target.registered_voters or 0
        total_registered += registered
        if registered and target.projected_turnout_pct:
            total_cast += round(registered * float(target.projected_turnout_pct) / 100)

        key = _unit_key(target)
        centre = target.registration_centre
        units.append(
            Unit(
                unit=centre.name if centre is not None else target.ward.name,
                needed=needed,
                committed=has,
                gap=max(needed - has, 0),
                progress=round(has / needed, 3) if needed else 0.0,
                events=events.get(key, 0),
                has_mobilizer=key in staffed,
            )
        )

    for unit in units:
        unit.share = round(unit.needed / win_number, 3) if win_number else 0.0

    return Strategy(
        win_number=win_number,
        committed=committed,
        progress_pct=round(committed / win_number * 100, 1) if win_number else 0.0,
        total_registered=total_registered,
        total_cast=total_cast,
        units=units,
        notes=_notes(units),
    )


def _unit_key(target: Target) -> tuple[str, str | None]:
    centre_id = target.registration_centre_id
    return (str(target.ward_id), str(centre_id) if centre_id is not None else None)


async def _events_per_unit(
    session: AsyncSession, targets: list[Target]
) -> dict[tuple[str, str | None], int]:
    """Events counted against the same unit each target covers.

    A ward-level target counts only ward-level events; a centre's events belong
    to the centre, not to the ward around it.
    """
    if not targets:
        return {}
    campaign_ids = {target.campaign_id for target in targets}
    rows = await session.execute(
        select(Event.ward_id, Event.registration_centre_id, func.count())
        .where(Event.campaign_id.in_(campaign_ids))
        .group_by(Event.ward_id, Event.registration_centre_id)
    )
    return {
        (str(ward_id), str(centre_id) if centre_id is not None else None): count
        for ward_id, centre_id, count in rows
    }


async def _staffed_units(
    session: AsyncSession, targets: list[Target]
) -> set[tuple[str, str | None]]:
    if not targets:
        return set()
    campaign_ids = {target.campaign_id for target in targets}
    rows = await session.execute(
        select(Mobilizer.ward_id, Mobilizer.registration_centre_id).where(
            Mobilizer.campaign_id.in_(campaign_ids)
        )
    )
    return {
        (str(ward_id), str(centre_id) if centre_id is not None else None)
        for ward_id, centre_id in rows
    }


def _notes(units: list[Unit]) -> list[Note]:
    """Three flags at most: where to go next, where to ease off, what is unstaffed."""
    notes: list[Note] = []

    behind = sorted((u for u in units if u.progress < 1), key=lambda u: -u.gap)
    if behind:
        worst = behind[0]
        reasons = [f"{round(worst.share * 100)}% of the win number is here"]
        if worst.events == 0:
            reasons.append("no events yet")
        elif worst.events < 2:
            reasons.append("only 1 event")
        if not worst.has_mobilizer:
            reasons.append("no mobilizer")
        notes.append(
            Note(
                tone="go",
                title=f"Go next: {worst.unit}",
                text=f"Biggest winnable gap - {worst.gap:,} votes short, "
                + ", ".join(reasons)
                + ".",
            )
        )

    over = next((u for u in units if u.progress >= 1 and u.events >= WELL_WORKED), None)
    if over is not None:
        notes.append(
            Note(
                tone="watch",
                title=f"Ease off: {over.unit}",
                text=(
                    f"Target met with {over.events} events - "
                    "spare effort is better spent elsewhere."
                ),
            )
        )

    unstaffed = [u.unit for u in units if not u.has_mobilizer]
    if unstaffed:
        notes.append(
            Note(
                tone="watch",
                title=f"{len(unstaffed)} unit{'s' if len(unstaffed) > 1 else ''} unstaffed",
                text=" and ".join(unstaffed[:6]) + " - no ground organiser to move the numbers.",
            )
        )

    return notes
