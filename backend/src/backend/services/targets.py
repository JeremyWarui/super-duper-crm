"""The wards a seat covers, and the vote targets built on them; re-running updates in place."""

import uuid
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    Campaign,
    Constituency,
    OfficeLevel,
    OperationalGrain,
    RegistrationCentre,
    Target,
    Ward,
    unit_key,
)
from backend.schemas.campaign import SetupSummary

WITH_COUNTY = selectinload(Ward.constituency).selectinload(Constituency.county)


def _in_area(statement: Select, campaign: Campaign) -> Select | None:
    """Narrow a ward query to a county or constituency seat, or None when no area is set."""
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


async def wards_in_area(session: AsyncSession, campaign: Campaign) -> list[Ward]:
    """Every ward inside the seat a campaign contests, by name, with its county loaded."""
    if campaign.office_level is OfficeLevel.WARD:
        if campaign.ward_id is None:
            return []
        ward = await session.scalar(
            select(Ward).where(Ward.id == campaign.ward_id).options(WITH_COUNTY)
        )
        return [ward] if ward is not None else []
    statement = _in_area(select(Ward).options(WITH_COUNTY), campaign)
    if statement is None:
        return []
    return list((await session.scalars(statement.order_by(Ward.name))).all())


async def generate_targets(session: AsyncSession, campaign: Campaign) -> SetupSummary:
    """Create or refresh a target per ward, or per centre for a ward race; committed votes stay.

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
    else:
        ward = wards[0] if wards else None
        centres = (
            await session.scalars(
                select(RegistrationCentre)
                .where(RegistrationCentre.ward_id == ward.id)
                .order_by(RegistrationCentre.name)
            )
            if ward is not None
            else []
        )
        units = [(ward, centre) for centre in centres]
        where = ward.name if ward is not None else "this campaign's ward"
        note = (
            None
            if units
            else f"No registration centres are loaded for {where} yet. "
            "Import them and run setup again to get centre targets."
        )

    total_registered = win_number = 0
    for ward, centre in units:
        centre_id = centre.id if centre is not None else None
        target = existing.get(unit_key(ward.id, centre_id))
        if target is None:
            target = Target(
                campaign_id=campaign.id, ward_id=ward.id, registration_centre_id=centre_id
            )
            session.add(target)
        target.ward = ward
        target.registration_centre = centre
        turnout: Decimal | None = ward.constituency.county.turnout_2022_pct
        target.projected_turnout_pct = turnout
        target.recompute_win_number()
        total_registered += (centre or ward).registered_voters or 0
        win_number += target.votes_needed or 0

    await session.flush()
    return SetupSummary(
        grain=grain,
        units=len(units),
        total_registered=total_registered,
        win_number=win_number,
        note=note,
    )
