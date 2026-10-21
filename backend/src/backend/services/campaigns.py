"""Building a campaign on its seat and area, with every target."""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Campaign,
    Constituency,
    County,
    OfficeLevel,
    RegistrationCentre,
    Seat,
    Ward,
)
from backend.schemas.campaign import SetupSummary
from backend.services.errors import Refused
from backend.services.targets import generate_targets

AREA_MODEL = {
    OfficeLevel.COUNTY: County,
    OfficeLevel.CONSTITUENCY: Constituency,
    OfficeLevel.WARD: Ward,
}
AREA_FIELD = {
    OfficeLevel.COUNTY: "county",
    OfficeLevel.CONSTITUENCY: "constituency",
    OfficeLevel.WARD: "ward",
}


async def build_campaign(
    session: AsyncSession,
    *,
    title: str,
    seat: Seat,
    election_date: date | None = None,
    county: uuid.UUID | None = None,
    constituency: uuid.UUID | None = None,
    ward: uuid.UUID | None = None,
) -> tuple[Campaign, SetupSummary]:
    """Create a campaign and its targets, without members and without committing."""
    office_level = seat.office_level
    area_field = AREA_FIELD[office_level]
    area_id = {"county": county, "constituency": constituency, "ward": ward}[area_field]
    if area_id is None:
        raise Refused(f"A {seat.label} campaign needs its {area_field} set.")
    if await session.get(AREA_MODEL[office_level], area_id) is None:
        raise Refused(f"No such {area_field}.")
    if office_level is OfficeLevel.WARD and not await session.scalar(
        select(RegistrationCentre.id).where(RegistrationCentre.ward_id == area_id).limit(1)
    ):
        raise Refused("That ward has no registration centres loaded; load the geography first.")

    campaign = Campaign(
        title=title,
        office_level=office_level,
        seat=seat,
        election_date=election_date,
        **{f"{area_field}_id": area_id},
    )
    session.add(campaign)
    await session.flush()
    return campaign, await generate_targets(session, campaign)
