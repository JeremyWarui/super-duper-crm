"""Turn a chosen seat into vote targets: a ward each, or a registration centre
each for a ward race. Re-running updates rather than adding.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
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
)


@dataclass
class TargetSummary:
    """`note` says why there are no units, when there are none."""

    grain: OperationalGrain
    units: int
    total_registered: int
    win_number: int
    note: str | None = None


async def _wards_for(session: AsyncSession, campaign: Campaign) -> list[Ward]:
    statement = select(Ward).options(
        selectinload(Ward.constituency).selectinload(Constituency.county)
    )
    if campaign.office_level is OfficeLevel.COUNTY and campaign.county_id is not None:
        statement = statement.join(Constituency).where(Constituency.county_id == campaign.county_id)
    elif campaign.office_level is OfficeLevel.CONSTITUENCY and campaign.constituency_id is not None:
        statement = statement.where(Ward.constituency_id == campaign.constituency_id)
    else:
        return []
    return list((await session.execute(statement.order_by(Ward.name))).scalars().all())


async def _existing_targets(session: AsyncSession, campaign: Campaign) -> dict[tuple, Target]:
    """The campaign's targets, keyed by the unit they cover."""
    statement = (
        select(Target)
        .where(Target.campaign_id == campaign.id)
        .options(selectinload(Target.ward), selectinload(Target.registration_centre))
    )
    return {
        (str(t.ward_id), str(t.registration_centre_id) if t.registration_centre_id else None): t
        for t in (await session.execute(statement)).scalars()
    }


async def generate_targets(session: AsyncSession, campaign: Campaign) -> TargetSummary:
    """Create or refresh every target, and total the win number.

    Committed votes are left alone.
    """
    grain = campaign.operational_grain
    existing = await _existing_targets(session, campaign)
    units = total_registered = win_number = 0
    note: str | None = None

    if grain is OperationalGrain.WARD:
        wards = await _wards_for(session, campaign)
        if not wards:
            note = "No area is set for this campaign's office level."
        for ward in wards:
            target = existing.get((str(ward.id), None))
            if target is None:
                target = Target(campaign_id=campaign.id, ward_id=ward.id)
                session.add(target)
            target.ward = ward
            target.registration_centre = None
            target.projected_turnout_pct = ward.constituency.county.turnout_2022_pct
            target.recompute_win_number()
            units += 1
            total_registered += ward.registered_voters or 0
            win_number += target.votes_needed or 0
    else:
        ward = await _campaign_ward(session, campaign)
        centres = await _centres_in(session, ward)
        turnout: Decimal | None = (
            ward.constituency.county.turnout_2022_pct if ward is not None else None
        )
        for centre in centres:
            target = existing.get((str(centre.ward_id), str(centre.id)))
            if target is None:
                target = Target(
                    campaign_id=campaign.id,
                    ward_id=centre.ward_id,
                    registration_centre_id=centre.id,
                )
                session.add(target)
            target.ward = ward
            target.registration_centre = centre
            target.projected_turnout_pct = turnout
            target.recompute_win_number()
            units += 1
            total_registered += centre.registered_voters or 0
            win_number += target.votes_needed or 0

        if units == 0:
            where = ward.name if ward is not None else "this campaign's ward"
            note = (
                f"No registration centres are loaded for {where} yet. "
                "Import them and run setup again to get centre targets."
            )

    await session.commit()
    return TargetSummary(
        grain=grain,
        units=units,
        total_registered=total_registered,
        win_number=win_number,
        note=note,
    )


async def _campaign_ward(session: AsyncSession, campaign: Campaign) -> Ward | None:
    if campaign.ward_id is None:
        return None
    statement = (
        select(Ward)
        .where(Ward.id == campaign.ward_id)
        .options(selectinload(Ward.constituency).selectinload(Constituency.county))
    )
    return (await session.execute(statement)).scalar_one_or_none()


async def _centres_in(session: AsyncSession, ward: Ward | None) -> list[RegistrationCentre]:
    if ward is None:
        return []
    statement = (
        select(RegistrationCentre)
        .where(RegistrationCentre.ward_id == ward.id)
        .order_by(RegistrationCentre.name)
    )
    return list((await session.execute(statement)).scalars().all())
