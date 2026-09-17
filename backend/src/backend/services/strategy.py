"""The strategy read, rolled up from targets, events and mobilizers on every request."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import Event, Mobilizer, Target, unit_key
from backend.schemas.strategy import NoteRead, StrategyRead, UnitRead

WELL_WORKED = 4


async def read_strategy(
    session: AsyncSession,
    *,
    campaign_ids: frozenset[uuid.UUID],
    campaign_id: uuid.UUID | None = None,
    ward_id: uuid.UUID | None = None,
) -> StrategyRead:
    """Roll the visible targets up, then say what stands out."""
    statement = (
        select(Target)
        .where(Target.campaign_id.in_(campaign_ids))
        .options(selectinload(Target.ward), selectinload(Target.registration_centre))
    )
    if campaign_id is not None:
        statement = statement.where(Target.campaign_id == campaign_id)
    if ward_id is not None:
        statement = statement.where(Target.ward_id == ward_id)
    targets = list((await session.scalars(statement)).all())

    seen = {t.campaign_id for t in targets}
    events = {
        unit_key(ward, centre): count
        for ward, centre, count in await session.execute(
            select(Event.ward_id, Event.registration_centre_id, func.count())
            .where(Event.campaign_id.in_(seen))
            .group_by(Event.ward_id, Event.registration_centre_id)
        )
    }
    staffed = {
        unit_key(ward, centre)
        for ward, centre in await session.execute(
            select(Mobilizer.ward_id, Mobilizer.registration_centre_id).where(
                Mobilizer.campaign_id.in_(seen)
            )
        )
    }

    units: list[UnitRead] = []
    committed = total_registered = total_cast = 0
    for target in targets:
        needed = target.votes_needed or 0
        has = target.votes_committed or 0
        committed += has
        registered = target.registered_voters or 0
        total_registered += registered
        if registered and target.projected_turnout_pct:
            total_cast += round(registered * float(target.projected_turnout_pct) / 100)
        key = unit_key(target.ward_id, target.registration_centre_id)
        centre = target.registration_centre
        units.append(
            UnitRead(
                unit=centre.name if centre is not None else target.ward.name,
                needed=needed,
                committed=has,
                gap=target.votes_remaining or 0,
                progress=round(has / needed, 3) if needed else 0.0,
                events=events.get(key, 0),
                has_mobilizer=key in staffed,
            )
        )

    win_number = sum(u.needed for u in units)
    for unit in units:
        unit.share = round(unit.needed / win_number, 3) if win_number else 0.0

    return StrategyRead(
        win_number=win_number,
        committed=committed,
        progress_pct=round(committed / win_number * 100, 1) if win_number else 0.0,
        total_registered=total_registered,
        total_cast=total_cast,
        units=units,
        notes=_notes(units),
    )


def _notes(units: list[UnitRead]) -> list[NoteRead]:
    """Where to go next, where to ease off, and what is unstaffed."""
    notes: list[NoteRead] = []

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
            NoteRead(
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
            NoteRead(
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
            NoteRead(
                tone="watch",
                title=f"{len(unstaffed)} unit{'s' if len(unstaffed) > 1 else ''} unstaffed",
                text=" and ".join(unstaffed[:6]) + " - no ground organiser to move the numbers.",
            )
        )

    return notes
