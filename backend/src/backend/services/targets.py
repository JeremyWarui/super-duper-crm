"""The wards a seat covers, and the vote targets built on them; re-running updates in place."""

import uuid
from decimal import Decimal
from fractions import Fraction

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    Campaign,
    Constituency,
    County,
    OfficeLevel,
    OperationalGrain,
    RegistrationCentre,
    Target,
    User,
    Ward,
    unit_key,
)
from backend.schemas.campaign import SetupSummary
from backend.services.audit import record
from backend.services.errors import Refused
from backend.services.geography import places
from backend.services.win_model import (
    as_decimal,
    expected_votes,
    fill_weights,
    load_history,
    seat_model,
    share_out,
    ward_valid_votes,
)

WITH_COUNTY = selectinload(Ward.constituency).selectinload(Constituency.county)


def _in_area(statement: Select, campaign: Campaign) -> Select | None:
    """Narrow a ward query to a county or constituency seat, leave it whole for the national
    scope, or None when no area is set."""
    if campaign.national:
        return statement
    if campaign.office_level is OfficeLevel.COUNTY and campaign.county_id is not None:
        return statement.join(Constituency).where(Constituency.county_id == campaign.county_id)
    if campaign.office_level is OfficeLevel.CONSTITUENCY and campaign.constituency_id is not None:
        return statement.where(Ward.constituency_id == campaign.constituency_id)
    return None


async def ward_in_area(session: AsyncSession, campaign: Campaign, ward_id: uuid.UUID) -> bool:
    """Whether a ward lies inside the seat a campaign contests."""
    if campaign.office_level is OfficeLevel.WARD:
        return campaign.ward_id == ward_id
    statement = _in_area(select(Ward.id).where(Ward.id == ward_id), campaign)
    return statement is not None and await session.scalar(statement) is not None


async def county_in_area(session: AsyncSession, campaign: Campaign, county_id: uuid.UUID) -> bool:
    """Whether a whole county lies inside the seat a campaign contests."""
    if campaign.national:
        return await session.get(County, county_id) is not None
    return campaign.office_level is OfficeLevel.COUNTY and campaign.county_id == county_id


async def constituency_in_area(
    session: AsyncSession, campaign: Campaign, constituency_id: uuid.UUID
) -> bool:
    """Whether a whole constituency lies inside the seat a campaign contests."""
    found = await session.get(Constituency, constituency_id)
    if found is None:
        return False
    if campaign.national:
        return True
    if campaign.office_level is OfficeLevel.COUNTY:
        return found.county_id == campaign.county_id
    return campaign.constituency_id == constituency_id


WARD_OUTSIDE = "That ward is not one this campaign works."
COUNTY_OUTSIDE = "That county is not one this campaign works as a whole."
CONSTITUENCY_OUTSIDE = "That constituency is not one this campaign works as a whole."
CENTRE_OUTSIDE = "That registration centre is not one this campaign works."
NO_TARGET = "That centre has no target, so work there would count toward nothing."


async def require_ward(
    session: AsyncSession, campaign: Campaign, ward_id: uuid.UUID | None
) -> None:
    """Refused unless the ward lies inside the campaign's seat."""
    if ward_id is None or not await ward_in_area(session, campaign, ward_id):
        raise Refused(WARD_OUTSIDE)


async def require_county(session: AsyncSession, campaign: Campaign, county_id: uuid.UUID) -> None:
    if not await county_in_area(session, campaign, county_id):
        raise Refused(COUNTY_OUTSIDE)


async def require_constituency(
    session: AsyncSession, campaign: Campaign, constituency_id: uuid.UUID
) -> None:
    if not await constituency_in_area(session, campaign, constituency_id):
        raise Refused(CONSTITUENCY_OUTSIDE)


async def require_centre(
    session: AsyncSession, campaign: Campaign, centre_id: uuid.UUID | None
) -> RegistrationCentre:
    """The registration centre, refused unless it lies in a ward of the campaign's seat."""
    centre = await session.get(RegistrationCentre, centre_id) if centre_id else None
    if centre is None or not await ward_in_area(session, campaign, centre.ward_id):
        raise Refused(CENTRE_OUTSIDE)
    return centre


async def require_targeted(
    session: AsyncSession, campaign_id: uuid.UUID, centre_id: uuid.UUID
) -> None:
    """Refused unless the campaign has a target at this centre."""
    targeted = await session.scalar(
        select(Target.id).where(
            Target.campaign_id == campaign_id, Target.registration_centre_id == centre_id
        )
    )
    if targeted is None:
        raise Refused(NO_TARGET)


async def wards_in_area(session: AsyncSession, campaign: Campaign) -> list[Ward]:
    """Every ward inside the seat a campaign contests, by name, with its county loaded."""
    if campaign.office_level is OfficeLevel.WARD:
        if campaign.ward_id is None:
            return []
        ward = await session.scalar(
            select(Ward).where(Ward.id == campaign.ward_id).options(WITH_COUNTY)
        )
        return [ward] if ward is not None else []
    statement = _in_area(select(Ward).where(Ward.retired.is_(False)).options(WITH_COUNTY), campaign)
    if statement is None:
        return []
    return list((await session.scalars(statement.order_by(Ward.name))).all())


async def ward_choices(session: AsyncSession, campaign: Campaign) -> list[Ward]:
    """The wards a public form lists in one go; none for a national seat, whose forms pick a
    county, then a constituency, then a ward."""
    return [] if campaign.national else await wards_in_area(session, campaign)


async def generate_targets(session: AsyncSession, campaign: Campaign) -> SetupSummary:
    """Work out the seat target from past results and share it out to a target per ward, or per
    centre for a ward race; committed votes stay (TD-R7 sections 4 and 5).

    Wards are weighted by their 2022 valid votes, centres by their register, and the shares add up
    to the seat target exactly. A target on a unit no longer in the seat is asked for nothing.

    Flushes; the caller commits.
    """
    existing = {
        unit_key(t.ward_id, t.registration_centre_id): t
        for t in await session.scalars(select(Target).where(Target.campaign_id == campaign.id))
    }
    wards = await wards_in_area(session, campaign)
    grain = campaign.operational_grain
    units: list[tuple[Ward, RegistrationCentre | None]]
    if grain is OperationalGrain.WARD:
        units = [(ward, None) for ward in wards]
        note = None if wards else "No area is set for this campaign's office level."
        valid = await ward_valid_votes(session, [ward.id for ward in wards])
        weights = fill_weights(
            {unit_key(w.id, None): valid[w.id] for w in wards},
            {unit_key(w.id, None): expected_votes(w) for w in wards},
        )
    else:
        ward = wards[0] if wards else None
        centres = await places(session, RegistrationCentre, ward.id) if ward is not None else []
        units = [(ward, centre) for centre in centres]
        note = None if units else "No registration centres are loaded for this campaign's ward."
        weights = {unit_key(c.ward_id, c.id): Fraction(c.registered_voters or 0) for c in centres}

    override = campaign.turnout_override_pct
    model = seat_model(
        await load_history(session, campaign, wards),
        turnout_override=Fraction(override) / 100 if override is not None else None,
    )
    projection = model.projection(campaign.turnout_scenario)
    seat_target = projection.target if units else 0
    shares = share_out(seat_target, weights)
    weight_sum = sum(weights.values(), Fraction(0)) or Fraction(1)

    total_registered = 0
    for ward, centre in units:
        key = unit_key(ward.id, centre.id if centre is not None else None)
        target = existing.pop(key, None)
        if target is None:
            target = Target(campaign_id=campaign.id, ward_id=key[0], registration_centre_id=key[1])
            session.add(target)
        target.ward = ward
        target.registration_centre = centre
        target.take_register()
        target.projected_turnout_pct = as_decimal(projection.turnout * 100, 2)
        target.turnout_scenario = projection.scenario
        target.turnout_overridden = model.overridden
        target.reliability = model.reliability
        target.ward_weight = as_decimal(weights[key] / weight_sum, 10)
        target.votes_needed = shares[key]
        total_registered += target.registered_voters or 0
    for stale in existing.values():
        stale.votes_needed = 0
        stale.ward_weight = Decimal(0)

    await session.flush()
    return SetupSummary(
        grain=grain,
        units=len(units),
        total_registered=total_registered,
        win_number=seat_target,
        note=note,
    )


async def recalculate_all(session: AsyncSession) -> int:
    """Rework every open campaign's targets, as after new results load; flushes."""
    campaigns = (await session.scalars(select(Campaign).where(Campaign.closed_at.is_(None)))).all()
    for campaign in campaigns:
        await generate_targets(session, campaign)
    return len(campaigns)


async def refresh_targets(
    session: AsyncSession, campaign: Campaign, *, actor: User
) -> SetupSummary:
    """Rework the targets from the current register and results, adding units new since the last
    refresh; votes committed stay. Imports never do this on their own."""
    summary = await generate_targets(session, campaign)
    # Every target the campaign has, so one left on a retired unit still counts.
    units, registered, needed = (
        await session.execute(
            select(
                func.count(Target.id),
                func.coalesce(func.sum(Target.registered_voters), 0),
                func.coalesce(func.sum(Target.votes_needed), 0),
            ).where(Target.campaign_id == campaign.id)
        )
    ).one()
    summary = summary.model_copy(
        update={"units": units, "total_registered": registered, "win_number": needed}
    )
    record(
        session,
        actor=actor,
        action="targets.refresh",
        subject_type="campaign",
        subject_id=campaign.id,
        campaign_id=campaign.id,
        detail={"units": summary.units, "win_number": summary.win_number},
    )
    await session.commit()
    return summary
