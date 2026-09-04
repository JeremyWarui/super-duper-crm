"""Load Kenya's electoral geography and the 2022 registered-voter figures.

Source: the processed GE2022 CSVs in `backend/data`
(github.com/nyimbi/kenya_election_data_2022, data/processed/csv).

Re-running matches rows and updates them, so it never duplicates.
"""

import csv
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import Constituency, County, RegistrationCentre, Ward

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


def rows(path: Path) -> Iterator[dict[str, str]]:
    """Rows with whitespace squeezed out of the headers and the values.

    The source spells one header "Constituency  Name", with two spaces.
    """
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return
        reader.fieldnames = [" ".join(name.split()).strip() for name in reader.fieldnames]
        for row in reader:
            yield {k: (v.strip() if isinstance(v, str) else "") for k, v in row.items()}


def to_int(value: str | None) -> int:
    """A count from the CSV, where blanks mean zero and thousands carry commas."""
    if value in (None, ""):
        return 0
    return int(str(value).replace(",", ""))


def normalise(name: str | None) -> str:
    """A name flattened for matching: one space between words, upper case."""
    return " ".join((name or "").split()).strip().upper()


async def import_geography(
    session: AsyncSession,
    *,
    caw: Path = CAW_CSV,
    county_voters: Path | None = COUNTY_VOTERS_CSV,
    county_results: Path | None = COUNTY_RESULTS_CSV,
) -> GeographySummary:
    """Counties, constituencies and wards, with registered voters and turnout.

    `caw` carries the whole tree. The two county files are optional and add the
    county voter totals and the 2022 turnout, which every win number defaults to.
    Computing turnout needs `county_voters`, because it is the denominator.
    """
    if county_results is not None and county_voters is None:
        raise ValueError("county_results needs county_voters: turnout divides by it.")

    counties: dict[str, County] = {}
    constituencies: dict[tuple[str, str], Constituency] = {}

    for existing in (await session.execute(select(County))).scalars():
        counties[existing.code] = existing
    for existing in (
        await session.execute(select(Constituency).options(selectinload(Constituency.county)))
    ).scalars():
        constituencies[(existing.county.code, normalise(existing.name))] = existing

    ward_index: dict[tuple[str, str], Ward] = {}
    for existing_ward in (
        await session.execute(select(Ward).options(selectinload(Ward.constituency)))
    ).scalars():
        ward_index[(str(existing_ward.constituency_id), normalise(existing_ward.name))] = (
            existing_ward
        )

    for row in rows(caw):
        county_code = str(to_int(row["County Code"]))
        county = counties.get(county_code)
        if county is None:
            county = County(code=county_code, name=row["County Name"])
            counties[county_code] = county
            session.add(county)
        else:
            county.name = row["County Name"]

        key = (county_code, normalise(row["Constituency Name"]))
        constituency = constituencies.get(key)
        if constituency is None:
            constituency = Constituency(
                county=county,
                name=row["Constituency Name"],
                code=str(to_int(row["Constituency Code"])),
            )
            constituencies[key] = constituency
            session.add(constituency)
        else:
            constituency.code = str(to_int(row["Constituency Code"]))

        ward_key = (str(constituency.id), normalise(row["County Assembly Ward Name"]))
        ward = ward_index.get(ward_key)
        if ward is None:
            ward = Ward(constituency=constituency, name=row["County Assembly Ward Name"])
            ward_index[ward_key] = ward
            session.add(ward)
        ward.code = row["County Assembly Code"]
        ward.registered_voters = to_int(row["Registered Voters"])

    await session.flush()

    if county_voters is not None:
        for row in rows(county_voters):
            county = counties.get(str(to_int(row["County Code"])))
            if county is not None:
                county.registered_voters = to_int(row["Registered Voters"])

    turnout_set = 0
    if county_results is not None:
        for row in rows(county_results):
            county = counties.get(str(to_int(row["County Code"])))
            # The file ends with diaspora and prison summary rows that match no county.
            if county is None or not county.registered_voters:
                continue
            cast = to_int(row.get("Total Valid Votes")) + to_int(row.get("Rejected"))
            pct = Decimal(cast * 100) / Decimal(county.registered_voters)
            county.turnout_2022_pct = pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            turnout_set += 1

    await session.commit()
    return GeographySummary(
        counties=len(counties),
        constituencies=len(constituencies),
        wards=len(ward_index),
        turnout_set=turnout_set,
    )


async def import_centres(session: AsyncSession, csv_path: Path = CENTRES_CSV) -> CentreSummary:
    """Registration centres, attached to their ward.

    Expects the columns `extract_polling_stations.py --centres` writes:
    county_code, const_name, ward_name, centre_code, centre_name, registered_voters.
    Run `import_geography` first, so there are wards to attach to.
    """
    ward_by_key: dict[tuple[str, str, str], Ward] = {}
    statement = select(Ward).options(
        selectinload(Ward.constituency).selectinload(Constituency.county)
    )
    for ward in (await session.execute(statement)).scalars():
        ward_by_key[
            (ward.constituency.county.code, normalise(ward.constituency.name), normalise(ward.name))
        ] = ward
    if not ward_by_key:
        raise ValueError("No wards loaded - run import_geography first.")

    existing: dict[tuple[str, str], RegistrationCentre] = {
        (str(centre.ward_id), centre.code): centre
        for centre in (await session.execute(select(RegistrationCentre))).scalars()
    }

    loaded = 0
    unmatched: list[tuple[str, str]] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is not None:
            reader.fieldnames = [name.strip().lower() for name in reader.fieldnames]
        for row in reader:
            key = (
                str(to_int(row.get("county_code"))),
                normalise(row.get("const_name")),
                normalise(row.get("ward_name")),
            )
            ward = ward_by_key.get(key)
            if ward is None:
                unmatched.append((row.get("ward_name") or "", row.get("centre_name") or ""))
                continue
            code = (row.get("centre_code") or "").strip()
            centre = existing.get((str(ward.id), code))
            if centre is None:
                centre = RegistrationCentre(ward=ward, code=code, name="")
                existing[(str(ward.id), code)] = centre
                session.add(centre)
            centre.name = (row.get("centre_name") or "").strip()
            centre.registered_voters = to_int(row.get("registered_voters"))
            loaded += 1

    await session.commit()
    return CentreSummary(
        centres=loaded,
        wards_covered=len({ward_id for ward_id, _ in existing}),
        unmatched=unmatched,
    )
