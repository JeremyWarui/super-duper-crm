"""The bundled CSVs load into the schema the models describe.

These run against the real files in `backend/data`, so a change to a header or a
column ordering fails here rather than on a deploy.
"""

from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import Campaign, Constituency, County, Mobilizer, Target, User, Ward
from backend.security import verify_password
from backend.seed.demo import DEMO_PASSWORDS, seed_demo
from backend.seed.reference import (
    CAW_CSV,
    COUNTY_RESULTS_CSV,
    COUNTY_VOTERS_CSV,
    import_centres,
    import_geography,
    normalise,
    rows,
    to_int,
)

# Published IEBC figures for the 2022 register.
KENYA_COUNTIES = 47
KENYA_CONSTITUENCIES = 290
KENYA_WARDS = 1450


def test_the_bundled_csvs_are_present() -> None:
    for path in (CAW_CSV, COUNTY_VOTERS_CSV, COUNTY_RESULTS_CSV):
        assert path.exists(), f"{path} is missing"


def test_headers_are_read_with_their_double_space_squeezed_out() -> None:
    """The source spells one header "Constituency  Name"."""
    first = next(rows(CAW_CSV))
    assert "Constituency Name" in first
    assert first["County Name"] == "Mombasa"


def test_a_count_reads_through_commas_and_blanks() -> None:
    assert to_int("17,817") == 17_817
    assert to_int("") == 0
    assert to_int(None) == 0


def test_names_match_regardless_of_case_and_spacing() -> None:
    assert normalise("  kahawa   west ") == normalise("Kahawa West") == "KAHAWA WEST"
    assert normalise(None) == ""


async def test_the_whole_country_loads(session: AsyncSession) -> None:
    summary = await import_geography(session)

    assert summary.counties == KENYA_COUNTIES
    assert summary.constituencies == KENYA_CONSTITUENCIES
    assert summary.wards == KENYA_WARDS
    assert await session.scalar(select(func.count()).select_from(Ward)) == KENYA_WARDS


async def test_registered_voters_match_the_published_figures(session: AsyncSession) -> None:
    await import_geography(session)
    mombasa = (await session.execute(select(County).where(County.name == "Mombasa"))).scalar_one()
    assert mombasa.registered_voters == 641_913

    port_reitz = (await session.execute(select(Ward).where(Ward.name == "Port Reitz"))).scalar_one()
    assert port_reitz.registered_voters == 17_817


async def test_turnout_is_votes_cast_over_the_register(session: AsyncSession) -> None:
    """Mombasa 2022: (277,301 valid + 3,812 rejected) / 641,913 = 43.79%."""
    await import_geography(session)
    mombasa = (await session.execute(select(County).where(County.name == "Mombasa"))).scalar_one()
    assert mombasa.turnout_2022_pct == Decimal("43.79")


async def test_every_county_gets_a_turnout(session: AsyncSession) -> None:
    summary = await import_geography(session)
    assert summary.turnout_set == KENYA_COUNTIES


async def test_turnout_needs_the_register_to_divide_by(session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="county_voters"):
        await import_geography(session, county_voters=None, county_results=COUNTY_RESULTS_CSV)


async def test_loading_twice_updates_rather_than_duplicates(session: AsyncSession) -> None:
    await import_geography(session)
    await import_geography(session)
    assert await session.scalar(select(func.count()).select_from(County)) == KENYA_COUNTIES
    assert await session.scalar(select(func.count()).select_from(Ward)) == KENYA_WARDS


async def test_centres_need_wards_first(session: AsyncSession, tmp_path) -> None:
    csv_path = tmp_path / "centres.csv"
    csv_path.write_text(
        "county_code,const_name,ward_name,centre_code,centre_name,registered_voters\n"
    )
    with pytest.raises(ValueError, match="import_geography first"):
        await import_centres(session, csv_path)


async def test_centres_attach_to_their_ward(session: AsyncSession, tmp_path) -> None:
    await import_geography(session)
    csv_path = tmp_path / "centres.csv"
    csv_path.write_text(
        "county_code,const_name,ward_name,centre_code,centre_name,registered_voters\n"
        "47,ROYSAMBU,Zimmerman,001,ZIMMERMAN PRIMARY SCHOOL,2500\n"
        "47,Roysambu,zimmerman,002,Roysambu Social Hall,1800\n"
        "99,Nowhere,Nowhere,003,Ghost Centre,100\n"
    )

    summary = await import_centres(session, csv_path)

    assert summary.centres == 2
    assert summary.unmatched == [("Nowhere", "Ghost Centre")]
    zimmerman = (
        await session.execute(
            select(Ward).where(Ward.name == "Zimmerman").options(selectinload(Ward.centres))
        )
    ).scalar_one()
    assert {c.name for c in zimmerman.centres} == {
        "ZIMMERMAN PRIMARY SCHOOL",
        "Roysambu Social Hall",
    }
    assert sum(c.registered_voters or 0 for c in zimmerman.centres) == 4_300


async def test_reloading_centres_updates_them_in_place(session: AsyncSession, tmp_path) -> None:
    await import_geography(session)
    csv_path = tmp_path / "centres.csv"
    header = "county_code,const_name,ward_name,centre_code,centre_name,registered_voters\n"
    csv_path.write_text(header + "47,Roysambu,Zimmerman,001,Zimmerman Primary,2500\n")
    await import_centres(session, csv_path)

    csv_path.write_text(header + "47,Roysambu,Zimmerman,001,Zimmerman Primary,2600\n")
    summary = await import_centres(session, csv_path)

    assert summary.centres == 1
    assert summary.wards_covered == 1


# ------------------------------------------------------------------- the demo


async def test_the_demo_needs_the_reference_data(session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="Roysambu"):
        await seed_demo(session)


async def test_the_demo_builds_one_campaign_with_one_sign_in_per_role(
    session: AsyncSession,
) -> None:
    await import_geography(session)

    summary = await seed_demo(session)

    assert summary.units > 0
    assert summary.win_number > 0
    assert [username for username, _, _ in summary.sign_ins] == [
        "aspirant",
        "manager",
        "mobilizer",
    ]


async def test_every_demo_password_signs_that_user_in(session: AsyncSession) -> None:
    await import_geography(session)
    await seed_demo(session)

    for username, password in DEMO_PASSWORDS.items():
        user = (await session.execute(select(User).where(User.username == username))).scalar_one()
        assert verify_password(password, user.password_hash), username


async def test_the_demo_mobilizer_is_tied_to_exactly_one_ward(session: AsyncSession) -> None:
    """Their whole app is scoped to it, so an unlinked mobilizer sees nothing."""
    await import_geography(session)
    await seed_demo(session)

    user = (
        await session.execute(
            select(User)
            .where(User.username == "mobilizer")
            .options(selectinload(User.mobilizer_profile))
        )
    ).scalar_one()
    assert user.mobilizer_profile is not None
    assert user.mobilizer_profile.ward_id is not None


async def test_the_demo_leaves_some_wards_unstaffed_and_some_targets_met(
    session: AsyncSession,
) -> None:
    """The strategy read has nothing to say when every unit looks the same."""
    await import_geography(session)
    await seed_demo(session)

    targets = (await session.execute(select(Target))).scalars().all()
    staffed = {str(m.ward_id) for m in (await session.execute(select(Mobilizer))).scalars().all()}
    assert 0 < len(staffed) < len(targets)
    assert any(t.votes_committed >= (t.votes_needed or 0) for t in targets)
    assert any(t.votes_committed == 0 for t in targets)


async def test_running_the_demo_twice_leaves_one_campaign(session: AsyncSession) -> None:
    await import_geography(session)
    await seed_demo(session)
    before = (await session.execute(select(func.count()).select_from(Target))).scalar_one()

    await seed_demo(session)

    assert await session.scalar(select(func.count()).select_from(Campaign)) == 1
    assert await session.scalar(select(func.count()).select_from(Target)) == before
    assert await session.scalar(select(func.count()).select_from(User)) == 3


async def test_the_demo_campaign_targets_every_ward_in_roysambu(session: AsyncSession) -> None:
    await import_geography(session)
    summary = await seed_demo(session)

    roysambu = (
        await session.execute(
            select(Constituency)
            .where(Constituency.name == "Roysambu")
            .options(selectinload(Constituency.wards))
        )
    ).scalar_one()
    assert summary.units == len(roysambu.wards)
