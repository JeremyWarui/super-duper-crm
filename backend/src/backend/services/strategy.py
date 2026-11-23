"""The strategy read, rolled up from targets, events and mobilizers on every request."""

import uuid
from typing import Literal

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    Campaign,
    Constituency,
    Event,
    Mobilizer,
    OfficeLevel,
    Supporter,
    SupportLevel,
    Target,
    Ward,
    unit_key,
)
from backend.schemas.strategy import GroupRead, NoteRead, StrategyRead, UnitRead
from backend.services.permissions import Area

WELL_WORKED = 4


async def read_strategy(
    session: AsyncSession,
    *,
    campaign_ids: frozenset[uuid.UUID],
    campaign_id: uuid.UUID | None = None,
    area: Area | None = None,
    county: uuid.UUID | None = None,
    constituency: uuid.UUID | None = None,
) -> StrategyRead:
    """Roll the visible targets up, then say what stands out.

    The totals, counts and notes cover every visible unit; `units` and `groups` only those in
    `county` or `constituency`.
    """
    statement = (
        select(Target)
        .where(Target.campaign_id.in_(campaign_ids))
        .options(
            selectinload(Target.ward)
            .selectinload(Ward.constituency)
            .selectinload(Constituency.county),
            selectinload(Target.registration_centre),
        )
    )
    if campaign_id is not None:
        statement = statement.where(Target.campaign_id == campaign_id)
    if area is not None:
        statement = statement.where(area.where(Target.ward_id, Target.registration_centre_id))
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
    by_ward: dict[uuid.UUID, int] = {}
    by_centre: dict[uuid.UUID, int] = {}
    supporter_rows = (
        await session.execute(
            select(Supporter.ward_id, Supporter.registration_centre_id, func.count())
            .where(
                Supporter.campaign_id.in_(seen), Supporter.support_level == SupportLevel.SUPPORTER
            )
            .group_by(Supporter.ward_id, Supporter.registration_centre_id)
        )
    ).all()
    for ward, centre, count in supporter_rows:
        by_ward[ward] = by_ward.get(ward, 0) + count
        if centre is not None:
            by_centre[centre] = count
    staffed = {
        unit_key(ward, centre)
        for ward, centre in await session.execute(
            select(Mobilizer.ward_id, Mobilizer.registration_centre_id).where(
                Mobilizer.campaign_id.in_(seen)
            )
        )
    }

    # In an MCA race a supporter counts only at a centre with a target; anyone else is unplaced.
    targeted = {t.registration_centre_id for t in targets if t.registration_centre_id is not None}
    in_mca = (
        select(Supporter.ward_id, Supporter.registration_centre_id, func.count())
        .join(Campaign, Campaign.id == Supporter.campaign_id)
        .where(
            Supporter.campaign_id.in_(campaign_ids),
            Supporter.support_level == SupportLevel.SUPPORTER,
            Campaign.office_level == OfficeLevel.WARD,
        )
        .group_by(Supporter.ward_id, Supporter.registration_centre_id)
    )
    if campaign_id is not None:
        in_mca = in_mca.where(Supporter.campaign_id == campaign_id)
    if area is not None:
        in_mca = in_mca.where(area.where(Supporter.ward_id, Supporter.registration_centre_id))
    unplaced = sum(
        count for ward, centre, count in await session.execute(in_mca) if centre not in targeted
    )

    units: list[UnitRead] = []
    committed = total_registered = total_cast = 0
    for target in targets:
        needed = target.votes_needed or 0
        # A ward target counts its whole ward; a centre target only that centre's supporters.
        centre_id = target.registration_centre_id
        has = by_ward.get(target.ward_id, 0) if centre_id is None else by_centre.get(centre_id, 0)
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
                ward=target.ward_id,
                constituency_name=target.ward.constituency.name,
                registration_centre=target.registration_centre_id,
                needed=needed,
                committed=has,
                gap=max(needed - has, 0),
                progress=round(has / needed, 3) if needed else 0.0,
                events=events.get(key, 0),
                has_mobilizer=key in staffed,
            )
        )

    win_number = sum(u.needed for u in units)
    for unit in units:
        unit.share = round(unit.needed / win_number, 3) if win_number else 0.0

    wards = {t.ward_id: t.ward for t in targets}
    asked = [
        u
        for u in units
        if (county is None or wards[u.ward].constituency.county_id == county)
        and (constituency is None or wards[u.ward].constituency_id == constituency)
    ]
    national = bool(seen) and bool(
        await session.scalar(
            select(
                exists().where(Campaign.id.in_(seen), Campaign.office_level == OfficeLevel.NATIONAL)
            )
        )
    )
    whole = national and county is None and constituency is None
    level: Literal["county", "constituency"] | None = None
    if whole:
        level = "county"
    elif constituency is None and len({wards[u.ward].constituency_id for u in asked}) > 1:
        level = "constituency"
    groups = _groups(asked, wards, level) if level else []

    return StrategyRead(
        win_number=win_number,
        committed=committed,
        progress_pct=round(committed / win_number * 100, 1) if win_number else 0.0,
        total_registered=total_registered,
        total_cast=total_cast,
        unit_count=len(units),
        short_count=sum(1 for u in units if u.gap > 0),
        staffed_count=sum(1 for u in units if u.has_mobilizer),
        quiet_count=sum(1 for u in units if u.events == 0),
        units=[] if whole else asked,
        group_level=level,
        groups=groups,
        notes=_notes(units, unplaced),
    )


def _groups(units: list[UnitRead], wards: dict[uuid.UUID, Ward], level: str) -> list[GroupRead]:
    """The units rolled up by county or by constituency, by name."""
    rolled: dict[uuid.UUID, GroupRead] = {}
    for unit in units:
        constituency = wards[unit.ward].constituency
        place = constituency.county if level == "county" else constituency
        group = rolled.get(place.id)
        if group is None:
            group = rolled[place.id] = GroupRead(
                id=place.id,
                name=place.name,
                units=0,
                needed=0,
                committed=0,
                gap=0,
                progress=0.0,
                unstaffed=0,
                quiet=0,
            )
        group.units += 1
        group.needed += unit.needed
        group.committed += unit.committed
        group.gap += unit.gap
        group.unstaffed += not unit.has_mobilizer
        group.quiet += unit.events == 0
    for group in rolled.values():
        group.progress = round(group.committed / group.needed, 3) if group.needed else 0.0
    return sorted(rolled.values(), key=lambda g: g.name)


def name_list(names: list[str], limit: int = 6) -> str:
    """Names as "A, B and C", the ones past `limit` counted as "and N more"."""
    shown, rest = names[:limit], len(names) - limit
    if rest > 0:
        return ", ".join(shown) + f" and {rest} more"
    return shown[0] if len(shown) == 1 else ", ".join(shown[:-1]) + f" and {shown[-1]}"


def _notes(units: list[UnitRead], unplaced: int = 0) -> list[NoteRead]:
    """Where to go next, where to ease off, what is unstaffed, and who needs a centre."""
    notes: list[NoteRead] = []

    if unplaced:
        who = f"{unplaced} supporters need" if unplaced > 1 else "1 supporter needs"
        notes.append(
            NoteRead(
                tone="watch",
                title=f"{who} a centre",
                text="They count toward no target until the manager or their mobilizer "
                "places them at a registration centre.",
            )
        )

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
                text=name_list(unstaffed) + " - no ground organiser to move the numbers.",
            )
        )

    return notes
