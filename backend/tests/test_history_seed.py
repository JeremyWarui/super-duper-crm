"""Past election results load from `backend/data/history`, link to today's places, and keep
figures that do not add up out of any target."""

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.cli import build_parser, run
from backend.models import (
    Contest,
    ContestCandidate,
    County,
    Election,
    ImportRun,
    ResultLevel,
    ResultOffice,
)
from backend.seed.history import RESULTS_CSV, area_code, import_results
from backend.seed.reference import import_geography

HEADER = (
    "record_id,year,election,race,county,county_code,constituency,constituency_code,ward,"
    "ward_code,candidate,party,votes,share_fraction,registered_voters,turnout_fraction,"
    "contest_total_votes,source_reference,data_note,election_status\n"
)


def row(**values: str) -> str:
    defaults = {
        "record_id": "r",
        "year": "2022",
        "election": "2022 General Election",
        "race": "governor",
        "county": "Laikipia",
        "county_code": "031",
        "constituency": "",
        "constituency_code": "",
        "ward": "",
        "ward_code": "",
        "candidate": "A",
        "party": "P",
        "votes": "10",
        "share_fraction": "",
        "registered_voters": "",
        "turnout_fraction": "",
        "contest_total_votes": "10",
        "source_reference": "",
        "data_note": "",
        "election_status": "",
    }
    defaults.update(values)
    return ",".join(f'"{defaults[k]}"' for k in HEADER.strip().split(",")) + "\n"


def write(tmp_path: Path, *rows: str) -> Path:
    path = tmp_path / "results.csv"
    path.write_text(HEADER + "".join(rows), encoding="utf-8")
    return path


async def governor(session: AsyncSession, election: str, county_code: str) -> Contest:
    return await session.scalar(
        select(Contest)
        .join(Election)
        .where(
            Election.name == election,
            Contest.office == ResultOffice.GOVERNOR,
            Contest.county_code == county_code,
        )
        .options(selectinload(Contest.candidates))
    )


def test_codes_lose_their_leading_zeros_as_the_geography_stores_them() -> None:
    assert (area_code("031"), area_code("0781"), area_code(""), area_code(" 7 ")) == (
        "31",
        "781",
        "",
        "7",
    )


@pytest.mark.skipif(not RESULTS_CSV.exists(), reason="the results file is not bundled")
async def test_the_whole_history_loads_and_links_to_todays_places(session: AsyncSession) -> None:
    await import_geography(session)
    summary = await import_results(session)

    assert (summary.elections, summary.contests, summary.candidates) == (5, 6069, 46607)
    assert summary.unlinked == 0
    # A handful of contests miss a candidate's votes or do not add up; none of them are targets.
    assert 0 < summary.excluded < 30
    assert await session.scalar(select(func.count(Contest.id)).where(Contest.excluded)) == (
        summary.excluded
    )

    years = {e.name: e.year for e in await session.scalars(select(Election))}
    assert years["2017 October Fresh Presidential Election"] == 2017
    assert set(years.values()) == {2013, 2017, 2022}

    statement = (
        select(Contest.level, func.count(Contest.id))
        .where(Contest.office == ResultOffice.MCA)
        .group_by(Contest.level)
    )
    by_level = {level: n for level, n in (await session.execute(statement)).all()}
    assert by_level == {ResultLevel.WARD: 1450 + 1447 + 1450}


@pytest.mark.skipif(not RESULTS_CSV.exists(), reason="the results file is not bundled")
async def test_laikipia_governor_matches_the_published_results(session: AsyncSession) -> None:
    await import_geography(session)
    await import_results(session)

    published = {
        "2013 General Election": ("JOSHUA WAKAHORA IRUNGU", 83678, 155699),
        "2017 General Election": ("MURIITHI NDIRITU", 100356, 198705),
        "2022 General Election": ("JOSHUA WAKAHORA IRUNGU", 113783, 167662),
    }
    laikipia = await session.scalar(select(County).where(County.code == "31"))
    for election, (winner, votes, total) in published.items():
        contest = await governor(session, election, "31")
        assert contest.county_id == laikipia.id
        assert contest.level is ResultLevel.COUNTY
        assert (contest.total_votes, contest.excluded) == (total, False)
        first = contest.candidates[0]
        assert (first.name, first.votes, first.rank, first.is_winner) == (winner, votes, 1, True)
        assert sum(c.is_winner for c in contest.candidates) == 1


@pytest.mark.skipif(not RESULTS_CSV.exists(), reason="the results file is not bundled")
async def test_an_unchanged_file_is_skipped_and_a_forced_reload_leaves_the_same_rows(
    session: AsyncSession,
) -> None:
    await import_geography(session)
    first = await import_results(session)
    await session.commit()

    assert (await import_results(session)).skipped
    again = await import_results(session, force=True)
    await session.commit()

    assert (again.contests, again.candidates, again.excluded) == (
        first.contests,
        first.candidates,
        first.excluded,
    )
    assert await session.scalar(select(func.count(Contest.id))) == first.contests
    assert await session.scalar(select(func.count(ContestCandidate.id))) == first.candidates
    assert await session.scalar(select(func.count(Election.id))) == 5
    runs = await session.scalar(select(func.count(ImportRun.id)).where(ImportRun.kind == "results"))
    assert runs == 2


async def test_figures_that_do_not_add_up_are_kept_but_excluded(
    session: AsyncSession, tmp_path: Path
) -> None:
    path = write(
        tmp_path,
        # Adds up: kept.
        row(county_code="031", candidate="A", votes="60", contest_total_votes="100"),
        row(county_code="031", candidate="B", votes="40", contest_total_votes="100"),
        # Candidates add up to 90 against a total of 100.
        row(county_code="030", candidate="C", votes="50", contest_total_votes="100"),
        row(county_code="030", candidate="D", votes="40", contest_total_votes="100"),
        # A candidate's votes are missing.
        row(county_code="029", candidate="E", votes="", contest_total_votes="100"),
        row(county_code="029", candidate="F", votes="100", contest_total_votes="100"),
    )
    summary = await import_results(session, path)

    assert (summary.contests, summary.excluded) == (3, 2)
    assert not (await governor(session, "2022 General Election", "31")).excluded
    short = await governor(session, "2022 General Election", "30")
    assert short.excluded
    assert "candidates add up to 90, the total says 100" in short.note
    missing = await governor(session, "2022 General Election", "29")
    assert (missing.excluded, "votes are missing" in missing.note) == (True, True)
    assert [c.rank for c in missing.candidates] == [1, None]


async def test_a_tie_crowns_nobody_and_a_lone_candidate_is_unopposed(
    session: AsyncSession, tmp_path: Path
) -> None:
    path = write(
        tmp_path,
        row(county_code="031", candidate="A", votes="50", contest_total_votes="100"),
        row(county_code="031", candidate="B", votes="50", contest_total_votes="100"),
        row(
            race="mca",
            county_code="031",
            constituency_code="160",
            ward_code="0795",
            ward="Igwamiti",
            candidate="C",
            votes="900",
            contest_total_votes="900",
            election_status="unopposed",
        ),
    )
    summary = await import_results(session, path)

    tie = await governor(session, "2022 General Election", "31")
    assert [c.is_winner for c in tie.candidates] == [False, False]
    assert summary.unopposed == 1
    ward = await session.scalar(select(Contest).where(Contest.office == ResultOffice.MCA))
    assert (ward.level, ward.ward_code, ward.area_name, ward.unopposed) == (
        ResultLevel.WARD,
        "795",
        "Igwamiti",
        True,
    )
    # No geography is loaded here, so nothing links.
    assert summary.unlinked == 2 and ward.ward_id is None


async def test_seed_results_needs_the_geography_first(
    session: AsyncSession, capsys: pytest.CaptureFixture
) -> None:
    args = build_parser().parse_args(["seed-results"])
    assert await run(args, session) == 1
    assert "Run campaign-crm seed first." in capsys.readouterr().out
