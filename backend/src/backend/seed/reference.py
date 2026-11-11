"""Load geography and registration centres from the IEBC files in `backend/data`.

The IEBC files are turned into a boundary file and a register file and loaded through
`services.imports`, so a first load and a console import write places the same way. Re-running
updates the places in place, matched by code.
"""

import csv
import io
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import Constituency, RegistrationCentre, Ward
from backend.services import imports

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
CAW_CSV = DATA_DIR / "ke_ge22_01_grv_caw_v100.csv"
COUNTY_VOTERS_CSV = DATA_DIR / "ke_ge22_03_grv_cty_v100.csv"
COUNTY_RESULTS_CSV = DATA_DIR / "ke_ge22_13_res_pre_cty_v100.csv"
CENTRES_CSV = DATA_DIR / "centres.csv"


@dataclass
class GeographySummary:
    counties: int
    constituencies: int
    wards: int
    turnout_set: int


@dataclass
class CentreSummary:
    centres: int
    wards_covered: int
    unmatched: list[tuple[str, str]]
    skipped_special: int = 0


def rows(path: Path, header: Callable[[str], str] | None = None) -> Iterator[dict[str, str]]:
    """CSV rows with stripped values; headers squeezed to single spaces, or through `header`."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return
        fix = header or (lambda name: " ".join(name.split()).strip())
        reader.fieldnames = [fix(name) for name in reader.fieldnames]
        for row in reader:
            yield {k: (v.strip() if isinstance(v, str) else "") for k, v in row.items()}


# Diaspora (48) and prisons (49): no ward, so their centres are skipped.
SPECIAL_COUNTY_CODES = {"48", "49"}

MIN_PREFIX_LENGTH = 8


def to_int(value: str | None) -> int:
    """A count. Blank is zero; thousands may carry commas."""
    if value in (None, ""):
        return 0
    return int(str(value).replace(",", ""))


# Apostrophe and slash variants the two IEBC files spell ward names with.
PUNCTUATION_VARIANTS = str.maketrans(
    {
        "’": "'",  # right single quotation mark
        "‘": "'",  # left single quotation mark
        "ʼ": "'",  # modifier letter apostrophe
        "´": "'",  # acute accent, used as one
        "`": "'",
        "\\": "/",
    }
)


def normalise(name: str | None) -> str:
    """A name flattened for matching: one space between words, upper case."""
    folded = (name or "").translate(PUNCTUATION_VARIANTS)
    return " ".join(folded.split()).strip().upper()


def _csv(columns: tuple[str, ...], lines: list[tuple]) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(columns)
    writer.writerows(lines)
    return out.getvalue()


async def _load(
    session: AsyncSession, boundaries: list[tuple], register: list[tuple], filename: str
) -> None:
    await imports.import_boundaries(
        session, _csv(imports.BOUNDARY_COLUMNS, boundaries), filename=filename, actor=None
    )
    if register:
        await imports.import_register(
            session, _csv(imports.REGISTER_COLUMNS, register), filename=filename, actor=None
        )


async def import_geography(
    session: AsyncSession,
    *,
    caw: Path = CAW_CSV,
    county_voters: Path | None = COUNTY_VOTERS_CSV,
    county_results: Path | None = COUNTY_RESULTS_CSV,
) -> GeographySummary:
    """Counties, constituencies and wards with registered voters, and each county's turnout."""
    if county_results is not None and county_voters is None:
        raise ValueError("county_results needs county_voters: turnout divides by it.")

    boundaries: list[tuple] = []
    register: list[tuple] = []
    counties: set[str] = set()
    constituencies: set[str] = set()
    for row in rows(caw):
        county = str(to_int(row["County Code"]))
        constituency = str(to_int(row["Constituency Code"]))
        ward = row["County Assembly Code"]
        counties.add(county)
        constituencies.add(constituency)
        boundaries.append(
            (
                county,
                row["County Name"],
                constituency,
                row["Constituency Name"],
                ward,
                row["County Assembly Ward Name"],
                "",
                "",
            )
        )
        register.append(("", ward, "", to_int(row["Registered Voters"]), ""))

    voters: dict[str, int] = {}
    if county_voters is not None:
        for row in rows(county_voters):
            county = str(to_int(row["County Code"]))
            if county in counties:
                voters[county] = to_int(row["Registered Voters"])

    turnout: dict[str, Decimal] = {}
    if county_results is not None:
        for row in rows(county_results):
            county = str(to_int(row["County Code"]))
            if not voters.get(county):
                continue
            cast = to_int(row.get("Total Valid Votes")) + to_int(row.get("Rejected"))
            pct = Decimal(cast * 100) / Decimal(voters[county])
            turnout[county] = pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    register += [(code, "", "", count, turnout.get(code, "")) for code, count in voters.items()]
    await _load(session, boundaries, register, caw.name)
    return GeographySummary(
        counties=len(counties),
        constituencies=len(constituencies),
        wards=len(boundaries),
        turnout_set=len(turnout),
    )


async def import_centres(session: AsyncSession, csv_path: Path = CENTRES_CSV) -> CentreSummary:
    """Registration centres, attached to their ward by name. Run `import_geography` first."""
    statement = (
        select(Ward)
        .where(Ward.retired.is_(False), Ward.code != "")
        .options(selectinload(Ward.constituency).selectinload(Constituency.county))
    )
    wards = list(await session.scalars(statement))
    if not wards:
        raise ValueError("No wards loaded - run import_geography first.")

    def place(ward: Ward) -> tuple[str, ...]:
        constituency = ward.constituency
        county = constituency.county
        return (
            county.code,
            county.name,
            constituency.code,
            constituency.name,
            ward.code,
            ward.name,
        )

    ward_by_key = {
        (w.constituency.county.code, normalise(w.constituency.name), normalise(w.name)): w
        for w in wards
    }
    # Every live ward is listed, so the import retires no ward the centres file leaves out.
    boundaries: list[tuple] = [(*place(w), "", "") for w in wards]
    register: list[tuple] = []
    skipped_special = 0
    unmatched: list[tuple[str, str]] = []
    for row in rows(csv_path, header=lambda name: name.strip().lower()):
        county_code = str(to_int(row.get("county_code")))
        if county_code in SPECIAL_COUNTY_CODES:
            skipped_special += 1
            continue
        key = (county_code, normalise(row.get("const_name")), normalise(row.get("ward_name")))
        ward = ward_by_key.get(key) or _match_truncated(ward_by_key, key)
        if ward is None:
            unmatched.append((row.get("ward_name") or "", row.get("centre_name") or ""))
            continue
        code = row.get("centre_code") or ""
        boundaries.append((*place(ward), code, row.get("centre_name") or ""))
        register.append(("", ward.code, code, to_int(row.get("registered_voters")), ""))

    await _load(session, boundaries, register, csv_path.name)
    covered = await session.scalar(
        select(func.count(func.distinct(RegistrationCentre.ward_id))).where(
            RegistrationCentre.retired.is_(False)
        )
    )
    return CentreSummary(
        centres=len(register),
        wards_covered=covered or 0,
        unmatched=unmatched,
        skipped_special=skipped_special,
    )


def _match_truncated(
    ward_by_key: dict[tuple[str, str, str], Ward], key: tuple[str, str, str]
) -> Ward | None:
    """The ward a clipped name was cut short of, when exactly one could be meant."""
    county_code, constituency, ward_name = key
    if len(ward_name) < MIN_PREFIX_LENGTH:
        return None
    candidates = [
        ward
        for (code, const, name), ward in ward_by_key.items()
        if code == county_code and const == constituency and name.startswith(ward_name)
    ]
    return candidates[0] if len(candidates) == 1 else None
