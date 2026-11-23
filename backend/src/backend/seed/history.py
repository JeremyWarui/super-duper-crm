"""Load past election results from `backend/data/history` into elections, contests and candidates.

The file is Kura254's historical results export (see `data/history/SOURCE.md`): one row per
candidate, the contest's valid-vote total repeated on every row. Loading replaces the contests of
every election the file names, so re-running it gives the same rows; an unchanged file is skipped.

A contest whose figures do not hold together is kept for reading and marked `excluded`, so no
target is built on it.
"""

import csv
import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Constituency,
    Contest,
    ContestCandidate,
    County,
    Election,
    ImportRun,
    ResultLevel,
    ResultOffice,
    Ward,
)
from backend.security import sha256_hex
from backend.seed.reference import DATA_DIR

RESULTS_CSV = DATA_DIR / "history" / "kura254_historical_results.csv"
IMPORT_KIND = "results"

# A contest's candidates may fall short of or exceed its total by this much before it is excluded.
TOLERANCE = 0.01

OFFICES = {
    "president": ResultOffice.PRESIDENT,
    "governor": ResultOffice.GOVERNOR,
    "senator": ResultOffice.SENATOR,
    "women_rep": ResultOffice.WOMEN_REP,
    "mp": ResultOffice.MP,
    "mca": ResultOffice.MCA,
}


@dataclass
class ResultsSummary:
    elections: int = 0
    contests: int = 0
    candidates: int = 0
    excluded: int = 0
    unopposed: int = 0
    unlinked: int = 0
    skipped: bool = False
    flags: list[str] = field(default_factory=list)


def area_code(value: str) -> str:
    """A code as the geography stores it: digits without leading zeros; blank stays blank."""
    value = (value or "").strip()
    return str(int(value)) if value.isdigit() else value


def count(value: str) -> int | None:
    """A vote or voter count; blank means unavailable, not zero."""
    value = (value or "").strip().replace(",", "")
    return int(value) if value else None


def level_of(county: str, constituency: str, ward: str) -> ResultLevel:
    if ward:
        return ResultLevel.WARD
    if constituency:
        return ResultLevel.CONSTITUENCY
    return ResultLevel.COUNTY


def year_of(name: str, year: str) -> int:
    return int(year) if year.isdigit() else int(name[:4])


@dataclass
class _Contest:
    election: str
    year: int
    office: ResultOffice
    county_code: str
    constituency_code: str
    ward_code: str
    area_name: str
    totals: set[int | None] = field(default_factory=set)
    registered: int | None = None
    unopposed: bool = False
    source_ref: str = ""
    candidates: list[tuple[str, str, int | None]] = field(default_factory=list)

    @property
    def level(self) -> ResultLevel:
        return level_of(self.county_code, self.constituency_code, self.ward_code)

    def problems(self) -> list[str]:
        """Why the figures cannot be trusted; empty when they hold together."""
        found: list[str] = []
        if len(self.totals) != 1:
            found.append("the contest total differs between candidate rows")
        total = next(iter(self.totals)) if len(self.totals) == 1 else None
        if total is None or total <= 0:
            found.append("no valid-vote total")
        if not self.candidates:
            found.append("no candidates")
        if any(votes is None for _, _, votes in self.candidates):
            found.append("a candidate's votes are missing")
        if total:
            added = sum(votes or 0 for _, _, votes in self.candidates)
            if abs(added - total) > max(1, TOLERANCE * total):
                found.append(f"candidates add up to {added:,}, the total says {total:,}")
        return found


def parse(path: Path) -> dict[tuple[str, ...], _Contest]:
    """The file's contests, keyed by election, office and area codes."""
    contests: dict[tuple[str, ...], _Contest] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            office = OFFICES.get(row["race"].strip().lower())
            if office is None:
                continue
            election = row["election"].strip()
            codes = (
                area_code(row["county_code"]),
                area_code(row["constituency_code"]),
                area_code(row["ward_code"]),
            )
            key = (election, office.value, *codes)
            contest = contests.get(key)
            if contest is None:
                level = level_of(*codes)
                name = {
                    ResultLevel.WARD: row["ward"],
                    ResultLevel.CONSTITUENCY: row["constituency"],
                    ResultLevel.COUNTY: row["county"],
                }[level]
                contest = contests[key] = _Contest(
                    election=election,
                    year=year_of(election, row["year"].strip()),
                    office=office,
                    county_code=codes[0],
                    constituency_code=codes[1],
                    ward_code=codes[2],
                    area_name=" ".join(name.split())[:100],
                    source_ref=row["record_id"].strip()[:200],
                )
            contest.totals.add(count(row["contest_total_votes"]))
            contest.registered = contest.registered or count(row["registered_voters"])
            contest.unopposed = contest.unopposed or row["election_status"].strip() == "unopposed"
            contest.candidates.append(
                (
                    " ".join(row["candidate"].split())[:200],
                    row["party"].strip()[:100],
                    count(row["votes"]),
                )
            )
    return contests


async def _places(session: AsyncSession, model: type) -> dict[str, uuid.UUID]:
    """Code to id; a live place wins over a retired one sharing its code."""
    found: dict[str, uuid.UUID] = {}
    rows = await session.execute(
        select(model.code, model.id, model.retired).where(model.code != "")
    )
    for code, place_id, _retired in sorted(rows.all(), key=lambda r: not r.retired):
        found[area_code(code)] = place_id
    return found


def _ranked(candidates: Iterable[tuple[str, str, int | None]]) -> list[dict]:
    """Candidates by votes, most first; rank 1 is the winner, ties share no win."""
    ordered = sorted(candidates, key=lambda c: -(c[2] if c[2] is not None else -1))
    top = ordered[0][2] if ordered else None
    leaders = sum(1 for c in ordered if c[2] is not None and c[2] == top)
    return [
        {
            "name": name,
            "party": party,
            "votes": votes,
            "rank": position if votes is not None else None,
            "is_winner": position == 1 and votes is not None and leaders == 1,
        }
        for position, (name, party, votes) in enumerate(ordered, start=1)
    ]


async def import_results(
    session: AsyncSession, csv_path: Path = RESULTS_CSV, *, force: bool = False
) -> ResultsSummary:
    """Replace the results of every election in the file; skipped when the file is unchanged.

    Run `import_geography` first so contests link to today's places. Flushes; the caller commits.
    """
    raw = csv_path.read_bytes()
    digest = sha256_hex(raw.decode("utf-8-sig"))
    last = await session.scalar(
        select(ImportRun.sha256)
        .where(ImportRun.kind == IMPORT_KIND)
        .order_by(ImportRun.created_at.desc())
        .limit(1)
    )
    if last == digest and not force:
        return ResultsSummary(skipped=True)

    parsed = parse(csv_path)
    counties = await _places(session, County)
    constituencies = await _places(session, Constituency)
    wards = await _places(session, Ward)

    names = sorted({c.election for c in parsed.values()})
    elections: dict[str, uuid.UUID] = {}
    for name in names:
        election = await session.scalar(select(Election).where(Election.name == name))
        year = next(c.year for c in parsed.values() if c.election == name)
        if election is None:
            election = Election(name=name, year=year)
            session.add(election)
            await session.flush()
        else:
            election.year = year
            await session.execute(delete(Contest).where(Contest.election_id == election.id))
        elections[name] = election.id

    summary = ResultsSummary(elections=len(names))
    contest_rows: list[dict] = []
    candidate_rows: list[dict] = []
    problems_by_kind: dict[str, int] = defaultdict(int)
    for contest in parsed.values():
        contest_id = uuid.uuid4()
        problems = contest.problems()
        total = next(iter(contest.totals)) if len(contest.totals) == 1 else None
        county_id = counties.get(contest.county_code) if contest.county_code else None
        constituency_id = (
            constituencies.get(contest.constituency_code) if contest.constituency_code else None
        )
        ward_id = wards.get(contest.ward_code) if contest.ward_code else None
        linked = {
            ResultLevel.COUNTY: county_id,
            ResultLevel.CONSTITUENCY: constituency_id,
            ResultLevel.WARD: ward_id,
        }[contest.level]
        if linked is None:
            summary.unlinked += 1
        unopposed = contest.unopposed or len(contest.candidates) == 1
        summary.unopposed += unopposed
        if problems:
            summary.excluded += 1
            for problem in problems:
                problems_by_kind[problem.split(" add up")[0]] += 1
            if len(summary.flags) < 20:
                summary.flags.append(
                    f"{contest.election} {contest.office.value} {contest.area_name}: "
                    + "; ".join(problems)
                )
        contest_rows.append(
            {
                "id": contest_id,
                "election_id": elections[contest.election],
                "office": contest.office,
                "level": contest.level,
                "county_code": contest.county_code,
                "constituency_code": contest.constituency_code,
                "ward_code": contest.ward_code,
                "county_id": county_id,
                "constituency_id": constituency_id,
                "ward_id": ward_id,
                "area_name": contest.area_name,
                "total_votes": total,
                "registered_voters": contest.registered,
                "unopposed": unopposed,
                "excluded": bool(problems),
                "note": "; ".join(problems),
                "source_ref": contest.source_ref,
            }
        )
        for candidate in _ranked(contest.candidates):
            candidate_rows.append({"id": uuid.uuid4(), "contest_id": contest_id, **candidate})

    if contest_rows:
        await session.execute(insert(Contest), contest_rows)
    if candidate_rows:
        await session.execute(insert(ContestCandidate), candidate_rows)
    summary.contests = len(contest_rows)
    summary.candidates = len(candidate_rows)

    session.add(
        ImportRun(
            kind=IMPORT_KIND,
            filename=csv_path.name[:255],
            sha256=digest,
            rows=summary.candidates,
            counts={
                "elections": summary.elections,
                "contests": summary.contests,
                "candidates": summary.candidates,
                "excluded": summary.excluded,
                "unopposed": summary.unopposed,
                "unlinked": summary.unlinked,
                "problems": dict(problems_by_kind),
            },
        )
    )
    await session.flush()
    return summary
