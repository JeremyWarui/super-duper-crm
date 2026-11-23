"""A seat's vote target from the share its last winner took (TD-R7 section 4).

Every figure is an exact fraction, so a result matches a hand calculation to the vote. The pure
functions come first; `load_history` reads what they need from the results tables.
"""

import math
import uuid
from collections import defaultdict
from collections.abc import Hashable, Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from statistics import median

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    Campaign,
    Constituency,
    Contest,
    Election,
    OfficeLevel,
    ResultLevel,
    ResultOffice,
    TargetReliability,
    TurnoutScenario,
    Ward,
)

HALF = Fraction(1, 2)
# Typical winner weights by election year.
WEIGHTS = {2013: Fraction(2, 10), 2017: Fraction(3, 10), 2022: Fraction(5, 10)}
LOW_ADJUSTMENT = Fraction(-3, 100)
# The top two's share of valid votes that makes a seat a two-candidate race.
TWO_CANDIDATE = Fraction(9, 10)

GENERAL = {year: f"{year} General Election" for year in (2013, 2017, 2022)}
# 2017 presidential turnout and share come from the August election.
PRESIDENTIAL_2017 = "2017 August Presidential Election"


@dataclass(frozen=True)
class Result:
    """One race's valid votes and its candidates' votes."""

    valid: int
    votes: tuple[int, ...]

    @property
    def ranked(self) -> tuple[int, ...]:
        return tuple(sorted(self.votes, reverse=True))

    @property
    def share(self) -> Fraction | None:
        """The winner's share of valid votes; None for a tie at the top or a lone candidate."""
        ranked = self.ranked
        if self.valid <= 0 or len(ranked) < 2 or ranked[0] == ranked[1]:
            return None
        return Fraction(ranked[0], self.valid)

    @property
    def two_candidate(self) -> bool:
        ranked = self.ranked
        return Fraction(sum(ranked[:2]), self.valid) >= TWO_CANDIDATE


@dataclass(frozen=True)
class SeatHistory:
    """Everything the calculation reads about one seat."""

    register: int
    # The seat's race by election year; a year with no usable race is left out.
    results: Mapping[int, Result]
    # Presidential valid votes ÷ registered voters in the seat's county (the country for
    # President), for the high scenario.
    turnout_2017: Fraction | None = None
    turnout_2022: Fraction | None = None
    # Turnout when the seat's own 2022 race gives none.
    fallback_turnout: Fraction | None = None
    # The national median 2022 winning share for the office.
    proxy_share: Fraction | None = None


@dataclass(frozen=True)
class Projection:
    """One turnout scenario worked through to a seat target."""

    scenario: TurnoutScenario
    adjustment: Fraction
    turnout: Fraction
    projected: int
    competitive: int
    majority: int
    target: int


@dataclass(frozen=True)
class SeatModel:
    share: Fraction
    reliability: TargetReliability
    typical: Fraction | None
    turnout: Fraction
    two_candidate: bool
    overridden: bool
    scenarios: Mapping[TurnoutScenario, Projection]
    uses_2017: bool

    def projection(self, scenario: TurnoutScenario) -> Projection:
        return self.scenarios[scenario]


def typical_winner(shares: Mapping[int, Fraction]) -> Fraction | None:
    """50% + Σ w(S − 50%) over the years present, the weights scaled to add up to one."""
    years = [year for year in WEIGHTS if year in shares]
    if not years:
        return None
    total = sum(WEIGHTS[year] for year in years)
    return HALF + sum(WEIGHTS[year] * (shares[year] - HALF) for year in years) / total


def nearest(value: Fraction) -> int:
    """Round to the nearest whole number, halves up."""
    return math.floor(value + HALF)


def high_adjustment(turnout_2017: Fraction | None, turnout_2022: Fraction | None) -> Fraction:
    """Half the fall in turnout from 2017 to 2022; nothing when it rose or is unknown."""
    if turnout_2017 is None or turnout_2022 is None or turnout_2017 <= turnout_2022:
        return Fraction(0)
    return (turnout_2017 - turnout_2022) / 2


def project(
    register: int,
    turnout: Fraction,
    share: Fraction,
    *,
    two_candidate: bool,
    scenario: TurnoutScenario,
    adjustment: Fraction,
) -> Projection:
    applied = min(max(turnout + adjustment, Fraction(0)), Fraction(1))
    projected = nearest(register * applied)
    competitive = math.ceil(projected * share)
    majority = projected // 2 + 1 if projected else 0
    target = max(competitive, majority) if two_candidate else competitive
    return Projection(scenario, adjustment, applied, projected, competitive, majority, target)


def seat_model(history: SeatHistory, *, turnout_override: Fraction | None = None) -> SeatModel:
    """Share, turnout and the three scenarios for one seat (section 4, steps 1 to 4).

    The share falls back to the typical winner, then to the office's national median (T8), and
    to 50% when no results are loaded at all. A turnout override replaces the seat's own turnout.
    """
    shares = {year: s for year, r in history.results.items() if (s := r.share) is not None}
    typical = typical_winner(shares)
    latest = history.results.get(2022)
    if 2022 in shares:
        share, reliability = shares[2022], TargetReliability.SEAT
    elif typical is not None:
        share, reliability = typical, TargetReliability.TYPICAL
    else:
        share, reliability = history.proxy_share or HALF, TargetReliability.PROXY

    turnout = history.fallback_turnout or Fraction(0)
    if latest is not None and latest.valid and history.register:
        turnout = Fraction(latest.valid, history.register)
    if turnout_override is not None:
        turnout = turnout_override
    # A seat with no 2022 race to judge by keeps the majority line as its floor.
    two_candidate = latest.two_candidate if latest is not None and latest.valid else True

    adjustments = {
        TurnoutScenario.LOW: LOW_ADJUSTMENT,
        TurnoutScenario.EXPECTED: Fraction(0),
        TurnoutScenario.HIGH: high_adjustment(history.turnout_2017, history.turnout_2022),
    }
    scenarios = {
        scenario: project(
            history.register,
            turnout,
            share,
            two_candidate=two_candidate,
            scenario=scenario,
            adjustment=adjustment,
        )
        for scenario, adjustment in adjustments.items()
    }
    return SeatModel(
        share=share,
        reliability=reliability,
        typical=typical,
        turnout=turnout,
        two_candidate=two_candidate,
        overridden=turnout_override is not None,
        scenarios=scenarios,
        uses_2017=2017 in shares or adjustments[TurnoutScenario.HIGH] > 0,
    )


def share_out[K: Hashable](total: int, weights: Mapping[K, Fraction]) -> dict[K, int]:
    """Split `total` by weight; each takes its whole part and the votes left over go one each to
    the largest fractions, so the parts add up to `total` exactly.

    Weights need not add up to one; they are scaled. Equal fractions go in the mapping's order.
    """
    weight_sum = sum(weights.values(), Fraction(0))
    if not weights:
        return {}
    if weight_sum <= 0:
        weights = {key: Fraction(1) for key in weights}
        weight_sum = Fraction(len(weights))
    exact = {key: total * w / weight_sum for key, w in weights.items()}
    parts = {key: math.floor(value) for key, value in exact.items()}
    left = total - sum(parts.values())
    order = sorted(exact, key=lambda key: exact[key] - parts[key], reverse=True)
    for key in order[:left]:
        parts[key] += 1
    return parts


def fill_weights[K: Hashable](
    valid: Mapping[K, int | None], expected: Mapping[K, Fraction]
) -> dict[K, Fraction]:
    """Each unit's 2022 valid votes; a unit with none takes its expected votes (register at its
    county's turnout), scaled to how the other units' valid votes compare with theirs."""
    known = {key: v for key, v in valid.items() if v}
    known_expected = sum((expected.get(key, Fraction(0)) for key in known), Fraction(0))
    rate = Fraction(sum(known.values())) / known_expected if known_expected else Fraction(1)
    return {
        key: Fraction(known[key]) if key in known else expected.get(key, Fraction(0)) * rate
        for key in valid
    }


def expected_votes(ward: Ward) -> Fraction:
    """A ward's register at its county's 2022 turnout, or its whole register when the turnout is
    unknown; needs the county loaded."""
    pct = ward.constituency.county.turnout_2022_pct
    return (ward.registered_voters or 0) * (Fraction(pct) / 100 if pct else Fraction(1))


def as_decimal(value: Fraction, places: int) -> Decimal:
    """A fraction rounded half up to `places` decimal places, for storage and display."""
    return Decimal(nearest(value * 10**places)).scaleb(-places)


# Reading the results tables.


def _result(contests: Iterable[Contest]) -> Result | None:
    """One race from its contests, adding up candidates by name when the race spans several
    contests (President by county); None when nothing usable is left."""
    valid = 0
    votes: dict[str, int] = defaultdict(int)
    for contest in contests:
        if contest.excluded or contest.unopposed or not contest.total_votes:
            continue
        valid += contest.total_votes
        for candidate in contest.candidates:
            votes[candidate.name] += candidate.votes or 0
    return Result(valid, tuple(votes.values())) if valid and votes else None


def _one_level(contests: list[Contest]) -> list[Contest]:
    """The contests at the widest level present, so a race reported at two levels counts once;
    2013 presidential results are held by constituency, later ones by county."""
    for level in (ResultLevel.COUNTY, ResultLevel.CONSTITUENCY, ResultLevel.WARD):
        found = [c for c in contests if c.level is level]
        if found:
            return found
    return []


def _turnout(contests: Iterable[Contest]) -> Fraction | None:
    usable = [c for c in contests if not c.excluded and c.total_votes and c.registered_voters]
    registered = sum(c.registered_voters or 0 for c in usable)
    return Fraction(sum(c.total_votes or 0 for c in usable), registered) if registered else None


async def _contests(session: AsyncSession, election: str, office: ResultOffice, *where) -> list:
    statement = (
        select(Contest)
        .join(Election)
        .where(Election.name == election, Contest.office == office, *where)
        .options(selectinload(Contest.candidates))
    )
    return list((await session.scalars(statement)).all())


def _seat_filter(campaign: Campaign) -> tuple:
    if campaign.office_level is OfficeLevel.WARD:
        return (Contest.ward_id == campaign.ward_id,)
    if campaign.office_level is OfficeLevel.CONSTITUENCY:
        return (Contest.constituency_id == campaign.constituency_id,)
    if campaign.office_level is OfficeLevel.COUNTY:
        return (Contest.county_id == campaign.county_id, Contest.ward_code == "")
    return ()


async def _county_id(session: AsyncSession, campaign: Campaign) -> uuid.UUID | None:
    if campaign.office_level is OfficeLevel.COUNTY:
        return campaign.county_id
    if campaign.office_level is OfficeLevel.CONSTITUENCY:
        return await session.scalar(
            select(Constituency.county_id).where(Constituency.id == campaign.constituency_id)
        )
    if campaign.office_level is OfficeLevel.WARD:
        return await session.scalar(
            select(Constituency.county_id)
            .join(Ward, Ward.constituency_id == Constituency.id)
            .where(Ward.id == campaign.ward_id)
        )
    return None


async def ward_valid_votes(
    session: AsyncSession, ward_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, int | None]:
    """Each ward's 2022 MCA valid votes, None where its race is unusable."""
    ids = list(ward_ids)
    found = {
        contest.ward_id: contest
        for contest in await _contests(
            session, GENERAL[2022], ResultOffice.MCA, Contest.ward_id.in_(ids)
        )
    }
    out: dict[uuid.UUID, int | None] = {}
    for ward_id in ids:
        contest = found.get(ward_id)
        usable = contest is not None and not contest.excluded and contest.total_votes
        out[ward_id] = contest.total_votes if usable else None
    return out


async def load_history(session: AsyncSession, campaign: Campaign, wards: list[Ward]) -> SeatHistory:
    """The seat's register (its wards' 2022 register), races and turnouts from the results;
    needs each ward's county loaded."""
    office = ResultOffice(campaign.seat.value)
    seat = _seat_filter(campaign)
    results: dict[int, Result] = {}
    for year, name in GENERAL.items():
        election = PRESIDENTIAL_2017 if office is ResultOffice.PRESIDENT and year == 2017 else name
        race = _result(_one_level(await _contests(session, election, office, *seat)))
        if race is not None:
            results[year] = race

    county_id = await _county_id(session, campaign)
    area = (Contest.county_id == county_id,) if county_id is not None else ()
    turnouts = [
        _turnout(await _contests(session, name, ResultOffice.PRESIDENT, *area))
        for name in (PRESIDENTIAL_2017, GENERAL[2022])
    ]

    register = sum(ward.registered_voters or 0 for ward in wards)
    valid = await ward_valid_votes(session, [ward.id for ward in wards])
    mca_valid = sum(v for v in valid.values() if v)
    fallback = Fraction(mca_valid, register) if mca_valid and register else None
    if fallback is None and register:
        counted = [w for w in wards if w.constituency.county.turnout_2022_pct]
        counted_register = sum(w.registered_voters or 0 for w in counted)
        if counted_register:
            fallback = sum(map(expected_votes, counted), Fraction(0)) / counted_register

    proxy = None
    if 2022 not in results or results[2022].share is None:
        shares = [
            share
            for contest in await _contests(session, GENERAL[2022], office)
            if (race := _result([contest])) is not None and (share := race.share) is not None
        ]
        proxy = Fraction(median(shares)) if shares else None

    return SeatHistory(
        register=register,
        results=results,
        turnout_2017=turnouts[0],
        turnout_2022=turnouts[1],
        fallback_turnout=fallback,
        proxy_share=proxy,
    )
