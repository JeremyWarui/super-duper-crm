"""Turning a seat into targets: which units, at what turnout, and what totals."""

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Constituency,
    County,
    OfficeLevel,
    OperationalGrain,
    RegistrationCentre,
    Target,
    User,
    Ward,
)
from backend.models.campaign import Campaign
from backend.services.targets import generate_targets


async def _county(session: AsyncSession, turnout: str | None = "60.00") -> County:
    county = County(
        name="Nairobi City",
        code="047",
        registered_voters=2_400_000,
        turnout_2022_pct=Decimal(turnout) if turnout else None,
    )
    session.add(county)
    await session.commit()
    return county


async def _campaign(session: AsyncSession, office_level: OfficeLevel, **area) -> Campaign:
    candidate = User(username=f"candidate-{office_level.value}")
    campaign = Campaign(
        candidate=candidate, title="Test campaign", office_level=office_level, **area
    )
    session.add(campaign)
    await session.commit()
    return campaign


async def test_an_mp_campaign_gets_one_target_per_ward_in_the_constituency(
    session: AsyncSession,
) -> None:
    county = await _county(session)
    constituency = Constituency(county=county, name="Roysambu", code="279")
    other = Constituency(county=county, name="Kasarani", code="278")
    session.add_all(
        [
            Ward(constituency=constituency, name="Zimmerman", registered_voters=30_701),
            Ward(constituency=constituency, name="Githurai", registered_voters=35_899),
            Ward(constituency=other, name="Clay City", registered_voters=20_000),
        ]
    )
    await session.commit()
    campaign = await _campaign(session, OfficeLevel.CONSTITUENCY, constituency_id=constituency.id)

    summary = await generate_targets(session, campaign)

    assert summary.grain is OperationalGrain.WARD
    assert summary.units == 2
    assert summary.total_registered == 66_600
    assert summary.note is None


async def test_a_governor_campaign_covers_every_ward_in_the_county(
    session: AsyncSession,
) -> None:
    county = await _county(session)
    for name in ("Roysambu", "Kasarani"):
        constituency = Constituency(county=county, name=name)
        session.add(Ward(constituency=constituency, name=f"{name} ward", registered_voters=10_000))
    await session.commit()
    campaign = await _campaign(session, OfficeLevel.COUNTY, county_id=county.id)

    summary = await generate_targets(session, campaign)

    assert summary.units == 2
    assert summary.total_registered == 20_000


async def test_each_ward_target_starts_at_its_county_turnout(session: AsyncSession) -> None:
    county = await _county(session, turnout="43.79")
    constituency = Constituency(county=county, name="Roysambu")
    session.add(Ward(constituency=constituency, name="Zimmerman", registered_voters=30_701))
    await session.commit()
    campaign = await _campaign(session, OfficeLevel.CONSTITUENCY, constituency_id=constituency.id)

    await generate_targets(session, campaign)

    target = (await session.execute(select(Target))).scalar_one()
    assert target.projected_turnout_pct == Decimal("43.79")


async def test_the_win_number_is_half_the_projected_votes_plus_one(
    session: AsyncSession,
) -> None:
    """30,701 on the roll at 60% is 18,420.6 cast, so 9,211 wins it."""
    county = await _county(session, turnout="60.00")
    constituency = Constituency(county=county, name="Roysambu")
    session.add(Ward(constituency=constituency, name="Zimmerman", registered_voters=30_701))
    await session.commit()
    campaign = await _campaign(session, OfficeLevel.CONSTITUENCY, constituency_id=constituency.id)

    summary = await generate_targets(session, campaign)

    assert summary.win_number == 9_211


async def test_an_mca_campaign_targets_the_centres_in_its_ward(session: AsyncSession) -> None:
    county = await _county(session)
    constituency = Constituency(county=county, name="Roysambu")
    ward = Ward(constituency=constituency, name="Zimmerman", registered_voters=30_701)
    session.add_all(
        [
            RegistrationCentre(
                ward=ward, name="Zimmerman Primary", code="1", registered_voters=2_500
            ),
            RegistrationCentre(ward=ward, name="Roysambu Hall", code="2", registered_voters=1_800),
        ]
    )
    await session.commit()
    campaign = await _campaign(session, OfficeLevel.WARD, ward_id=ward.id)

    summary = await generate_targets(session, campaign)

    assert summary.grain is OperationalGrain.CENTRE
    assert summary.units == 2
    assert summary.total_registered == 4_300
    targets = (await session.execute(select(Target))).scalars().all()
    assert all(t.registration_centre_id is not None for t in targets)


async def test_a_ward_with_no_centres_loaded_says_so_rather_than_looking_finished(
    session: AsyncSession,
) -> None:
    county = await _county(session)
    constituency = Constituency(county=county, name="Roysambu")
    ward = Ward(constituency=constituency, name="Zimmerman", registered_voters=30_701)
    session.add(ward)
    await session.commit()
    campaign = await _campaign(session, OfficeLevel.WARD, ward_id=ward.id)

    summary = await generate_targets(session, campaign)

    assert summary.units == 0
    assert summary.win_number == 0
    assert summary.note is not None
    assert "Zimmerman" in summary.note


async def test_a_campaign_with_no_area_set_says_so(session: AsyncSession) -> None:
    await _county(session)
    campaign = await _campaign(session, OfficeLevel.CONSTITUENCY)

    summary = await generate_targets(session, campaign)

    assert summary.units == 0
    assert summary.note == "No area is set for this campaign's office level."


async def test_a_county_with_no_recorded_turnout_leaves_the_win_number_open(
    session: AsyncSession,
) -> None:
    county = await _county(session, turnout=None)
    constituency = Constituency(county=county, name="Roysambu")
    session.add(Ward(constituency=constituency, name="Zimmerman", registered_voters=30_701))
    await session.commit()
    campaign = await _campaign(session, OfficeLevel.CONSTITUENCY, constituency_id=constituency.id)

    summary = await generate_targets(session, campaign)

    assert summary.units == 1
    assert summary.win_number == 0
    target = (await session.execute(select(Target))).scalar_one()
    assert target.votes_needed is None


async def test_running_it_again_updates_the_targets_rather_than_adding_more(
    session: AsyncSession,
) -> None:
    county = await _county(session)
    constituency = Constituency(county=county, name="Roysambu")
    session.add(Ward(constituency=constituency, name="Zimmerman", registered_voters=30_701))
    await session.commit()
    campaign = await _campaign(session, OfficeLevel.CONSTITUENCY, constituency_id=constituency.id)
    await generate_targets(session, campaign)

    await generate_targets(session, campaign)

    assert await session.scalar(select(func.count()).select_from(Target)) == 1


async def test_running_it_again_keeps_the_votes_already_committed(
    session: AsyncSession,
) -> None:
    county = await _county(session)
    constituency = Constituency(county=county, name="Roysambu")
    session.add(Ward(constituency=constituency, name="Zimmerman", registered_voters=30_701))
    await session.commit()
    campaign = await _campaign(session, OfficeLevel.CONSTITUENCY, constituency_id=constituency.id)
    await generate_targets(session, campaign)
    target = (await session.execute(select(Target))).scalar_one()
    target.votes_committed = 4_000
    await session.commit()

    await generate_targets(session, campaign)

    await session.refresh(target)
    assert target.votes_committed == 4_000


async def test_a_new_ward_appearing_later_gets_its_own_target(session: AsyncSession) -> None:
    county = await _county(session)
    constituency = Constituency(county=county, name="Roysambu")
    session.add(Ward(constituency=constituency, name="Zimmerman", registered_voters=30_701))
    await session.commit()
    campaign = await _campaign(session, OfficeLevel.CONSTITUENCY, constituency_id=constituency.id)
    await generate_targets(session, campaign)

    session.add(Ward(constituency=constituency, name="Githurai", registered_voters=35_899))
    await session.commit()
    summary = await generate_targets(session, campaign)

    assert summary.units == 2
    assert await session.scalar(select(func.count()).select_from(Target)) == 2
