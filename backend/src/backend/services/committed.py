"""Votes committed: the contacts marked Supporter in a unit, counted live. Every screen that shows
supporters against a target reads this, so they all agree."""

import uuid
from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value

from backend.models import Supporter, SupportLevel, Target


class Counts:
    """Supporters per ward and per registration centre."""

    def __init__(self, by_ward: dict[uuid.UUID, int], by_centre: dict[uuid.UUID, int]) -> None:
        self.by_ward = by_ward
        self.by_centre = by_centre

    def of(self, ward_id: uuid.UUID | None, centre_id: uuid.UUID | None) -> int:
        """A ward target counts its whole ward; a centre target only that centre's supporters."""
        if centre_id is not None:
            return self.by_centre.get(centre_id, 0)
        return self.by_ward.get(ward_id, 0) if ward_id is not None else 0


async def counts(session: AsyncSession, campaign_ids: Iterable[uuid.UUID]) -> Counts:
    ids = set(campaign_ids)
    by_ward: dict[uuid.UUID, int] = {}
    by_centre: dict[uuid.UUID, int] = {}
    if not ids:
        return Counts(by_ward, by_centre)
    rows = await session.execute(
        select(Supporter.ward_id, Supporter.registration_centre_id, func.count())
        .where(
            Supporter.campaign_id.in_(ids),
            Supporter.support_level == SupportLevel.SUPPORTER,
        )
        .group_by(Supporter.ward_id, Supporter.registration_centre_id)
    )
    for ward, centre, count in rows:
        if ward is not None:
            by_ward[ward] = by_ward.get(ward, 0) + count
        if centre is not None:
            by_centre[centre] = by_centre.get(centre, 0) + count
    return Counts(by_ward, by_centre)


async def fill(session: AsyncSession, targets: list[Target]) -> list[Target]:
    """Set each target's votes committed to the live count, in memory only (never saved)."""
    live = await counts(session, {t.campaign_id for t in targets})
    for target in targets:
        set_committed_value(
            target,
            "votes_committed",
            live.of(target.ward_id, target.registration_centre_id),
        )
    return targets
