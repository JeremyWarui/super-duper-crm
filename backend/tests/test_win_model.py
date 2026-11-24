"""Seat targets from the last winner's share: the worked examples in TD-R7 section 4."""

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    County,
    OfficeLevel,
    Seat,
    Target,
    TargetReliability,
    TurnoutScenario,
    Ward,
)
from backend.models.campaign import Campaign
from backend.seed.history import RESULTS_CSV, import_results
from backend.seed.reference import import_centres, import_geography
from backend.services.targets import generate_targets, recalculate_all, wards_in_area
from backend.services.win_model import as_decimal, load_history, seat_model

pytestmark = pytest.mark.skipif(not RESULTS_CSV.exists(), reason="the results file is not bundled")

LOW, EXPECTED, HIGH = TurnoutScenario.LOW, TurnoutScenario.EXPECTED, TurnoutScenario.HIGH

# County code: share, turnout, two-candidate, typical winner, and per scenario
# (turnout, P, C, F, seat target), as printed in sections 4.1 and 4.2.
WORKED = {
    "31": (
        "67.86",
        "63.75",
        True,
        "59.83",
        {
            LOW: ("60.75", 159_772, 108_429, 79_887, 108_429),
            EXPECTED: ("63.75", 167_662, 113_783, 83_832, 113_783),
            HIGH: ("72.07", 189_553, 128_640, 94_777, 128_640),
        },
    ),
    "10": (
        "33.80",
        "68.77",
        False,
        "42.95",
        {
            LOW: ("65.77", 109_782, 37_111, 54_892, 37_111),
            EXPECTED: ("68.77", 114_789, 38_803, 57_395, 38_803),
            HIGH: ("73.46", 122_614, 41_449, 61_308, 41_449),
        },
    ),
}

LAIKIPIA_WARDS = {
    "Igwamiti": 17_870,
    "Marmanet": 11_920,
    "Nanyuki": 11_674,
    "Tigithi": 9_974,
    "Ngobit": 8_115,
    "Thingithu": 7_970,
    "Githiga": 7_426,
    "Sosian": 6_594,
    "Rumuruti Township": 6_123,
    "Umande": 5_385,
    "Mugogodo East": 4_927,
    "Ol-Moran": 4_474,
    "Segera": 4_264,
    "Salama": 4_159,
    "Mugogodo West": 2_908,
}


def pct(value) -> str:  # type: ignore[no-untyped-def]
    return str(as_decimal(value * 100, 2))


async def governor(session: AsyncSession, county_code: str) -> Campaign:
    county = await session.scalar(select(County).where(County.code == county_code))
    campaign = Campaign(
        title="Governor", office_level=OfficeLevel.COUNTY, seat=Seat.GOVERNOR, county_id=county.id
    )
    session.add(campaign)
    await session.commit()
    return campaign


async def test_laikipia_and_marsabit_give_every_figure_in_the_worked_examples(
    session: AsyncSession,
) -> None:
    await import_geography(session)
    await import_results(session)

    for code, (share, turnout, two, typical, scenarios) in WORKED.items():
        campaign = await governor(session, code)
        history = await load_history(session, campaign, await wards_in_area(session, campaign))
        model = seat_model(history)

        assert (pct(model.share), pct(model.turnout)) == (share, turnout), code
        assert (model.two_candidate, pct(model.typical)) == (two, typical), code
        assert model.reliability is TargetReliability.SEAT
        for scenario, figures in scenarios.items():
            p = model.projection(scenario)
            assert (pct(p.turnout), p.projected, p.competitive, p.majority, p.target) == figures

    president = Campaign(title="President", office_level=OfficeLevel.NATIONAL, seat=Seat.PRESIDENT)
    history = await load_history(session, president, [])
    assert set(history.results) == {2013, 2017, 2022}


async def test_ward_targets_reproduce_the_laikipia_table_and_add_up_to_the_seat_target(
    session: AsyncSession,
) -> None:
    await import_geography(session)
    campaign = await governor(session, "31")
    await generate_targets(session, campaign)
    await session.commit()

    # A campaign that existed before the results loaded is reworked by the load.
    await import_results(session)
    assert await recalculate_all(session) == 1
    await session.commit()

    targets = (
        await session.scalars(
            select(Target)
            .where(Target.campaign_id == campaign.id)
            .options(selectinload(Target.ward))
        )
    ).all()
    assert {t.ward.name: t.votes_needed for t in targets} == LAIKIPIA_WARDS
    assert {t.reliability for t in targets} == {TargetReliability.SEAT}
    assert targets[0].projected_turnout_pct == Decimal("63.75")

    campaign.turnout_scenario = HIGH
    summary = await generate_targets(session, campaign)
    await session.commit()
    needed = await session.scalars(
        select(Target.votes_needed).where(Target.campaign_id == campaign.id)
    )
    assert summary.win_number == sum(needed) == 128_640


async def test_an_mca_seat_s_centre_targets_add_up_to_its_seat_target(
    session: AsyncSession,
) -> None:
    await import_geography(session)
    await import_centres(session)
    await import_results(session)
    ward = await session.scalar(select(Ward).where(Ward.name == "Ol-Moran"))
    campaign = Campaign(title="MCA", office_level=OfficeLevel.WARD, seat=Seat.MCA, ward_id=ward.id)
    session.add(campaign)
    await session.flush()

    summary = await generate_targets(session, campaign)
    centres = (
        await session.scalars(select(Target.votes_needed).where(Target.campaign_id == campaign.id))
    ).all()

    assert summary.units == len(centres) > 1
    assert sum(centres) == summary.win_number > 0
