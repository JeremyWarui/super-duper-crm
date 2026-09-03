"""Minimal object builders, so each test states only what it cares about."""

from backend.models import (
    Campaign,
    Constituency,
    County,
    Mobilizer,
    OfficeLevel,
    RegistrationCentre,
    User,
    Ward,
)


async def make_geography(session, *, ward_voters: int | None = 10_000):
    """County -> Constituency -> Ward -> RegistrationCentre, committed."""
    county = County(name="Nairobi", code="047", registered_voters=2_400_000)
    constituency = Constituency(county=county, name="Westlands", code="274")
    ward = Ward(
        constituency=constituency, name="Parklands", code="1370", registered_voters=ward_voters
    )
    centre = RegistrationCentre(
        ward=ward, name="Parklands Primary", code="001", registered_voters=2_000
    )
    session.add(county)
    await session.commit()
    return county, constituency, ward, centre


async def make_campaign(session, ward: Ward, *, office_level=OfficeLevel.WARD) -> Campaign:
    candidate = User(username=f"candidate-{ward.code}", first_name="Asha", last_name="Mwangi")
    campaign = Campaign(
        candidate=candidate,
        title=f"{ward.name} MCA 2027",
        office_level=office_level,
        ward=ward,
    )
    session.add(campaign)
    await session.commit()
    return campaign


async def make_mobilizer(session, campaign: Campaign, ward: Ward) -> Mobilizer:
    mobilizer = Mobilizer(
        campaign=campaign, ward=ward, full_name="Juma Otieno", phone="+254700000000"
    )
    session.add(mobilizer)
    await session.commit()
    return mobilizer
