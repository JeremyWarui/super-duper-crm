"""Boundary and voter register imports from CSV.

Every row is checked before anything is written; one bad row and the file changes nothing.
Areas are matched by code: counties, constituencies and wards by their own code, a centre by its
ward's code and its own. An import never deletes an area; one left out of a boundary file is
retired, which hides it from pickers and keeps everything that refers to it.
"""

import csv
import io
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Constituency,
    County,
    ImportChange,
    ImportRun,
    RegistrationCentre,
    User,
    Ward,
)
from backend.security import sha256_hex
from backend.services.audit import record
from backend.services.errors import Refused

BOUNDARY_COLUMNS = (
    "county_code",
    "county_name",
    "constituency_code",
    "constituency_name",
    "ward_code",
    "ward_name",
    "centre_code",
    "centre_name",
)
REGISTER_COLUMNS = ("county_code", "ward_code", "centre_code", "registered_voters", "turnout_pct")
LENGTHS = {
    "county_code": 10,
    "constituency_code": 10,
    "ward_code": 10,
    "centre_code": 30,
    "county_name": 100,
    "constituency_name": 100,
    "ward_name": 100,
    "centre_name": 200,
}
MAX_ERRORS = 50


class ImportRefused(Refused):
    """The file failed its checks; `errors` names each bad line."""

    def __init__(self, errors: list[str]) -> None:
        shown = errors[:MAX_ERRORS]
        more = f" (and {len(errors) - MAX_ERRORS} more)" if len(errors) > MAX_ERRORS else ""
        super().__init__("Nothing was imported. " + " ".join(shown) + more)
        self.errors = errors


@dataclass
class Change:
    level: str
    code: str
    change: str
    detail: str = ""


@dataclass
class ImportReport:
    kind: str
    rows: int
    changes: list[Change] = field(default_factory=list)
    applied: bool = False

    @property
    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for c in self.changes:
            out[c.change] = out.get(c.change, 0) + 1
        return out


def _read(text: str, columns: tuple[str, ...]) -> list[dict[str, str]]:
    """The rows, keyed by lower-case trimmed header, every value trimmed."""
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    if reader.fieldnames is None:
        raise ImportRefused(["The file is empty."])
    headers = [(h or "").strip().lower() for h in reader.fieldnames]
    missing = [c for c in columns if c not in headers]
    if missing:
        raise ImportRefused([f"The header row lacks: {', '.join(missing)}."])
    rows = []
    for raw in reader:
        row = {
            (k or "").strip().lower(): (v or "").strip()
            for k, v in raw.items()
            if not isinstance(v, list)
        }
        if any(row.values()):
            rows.append(row)
    if not rows:
        raise ImportRefused(["The file has a header and no rows."])
    return rows


def _check_lengths(line: int, row: dict[str, str], errors: list[str]) -> None:
    for name, limit in LENGTHS.items():
        if len(row.get(name, "")) > limit:
            errors.append(f"Line {line}: {name} is longer than {limit} characters.")


def _agree(
    seen: dict, key, value: tuple, line: int, what: str, errors: list[str], label: str = ""
) -> None:
    """Every row naming `key` must give it the same `value`; `label` names it in the refusal."""
    first = seen.setdefault(key, (value, line))
    if first[0] != value:
        errors.append(f"Line {line}: {what} {label or key} differs from line {first[1]}.")


# Boundaries


async def import_boundaries(
    session: AsyncSession,
    text: str,
    *,
    filename: str = "",
    actor: User | None,
    dry_run: bool = False,
) -> ImportReport:
    """Upsert counties, constituencies, wards and centres from a boundary file.

    Inside the counties the file covers, a constituency or ward it leaves out is retired, and so
    is a centre left out of a ward the file lists centres for.
    """
    rows = _read(text, BOUNDARY_COLUMNS)
    errors: list[str] = []
    counties: dict[str, tuple] = {}
    constituencies: dict[str, tuple] = {}
    wards: dict[str, tuple] = {}
    centres: dict[tuple[str, str], tuple] = {}
    for line, row in enumerate(rows, start=2):
        _check_lengths(line, row, errors)
        needed = [c for c in BOUNDARY_COLUMNS[:6] if not row[c]]
        if needed:
            errors.append(f"Line {line}: {', '.join(needed)} missing.")
            continue
        if bool(row["centre_code"]) != bool(row["centre_name"]):
            errors.append(f"Line {line}: a centre needs both centre_code and centre_name.")
            continue
        _agree(counties, row["county_code"], (row["county_name"],), line, "county", errors)
        _agree(
            constituencies,
            row["constituency_code"],
            (row["constituency_name"], row["county_code"]),
            line,
            "constituency",
            errors,
        )
        _agree(
            wards,
            row["ward_code"],
            (row["ward_name"], row["constituency_code"]),
            line,
            "ward",
            errors,
        )
        if row["centre_code"]:
            _agree(
                centres,
                (row["ward_code"], row["centre_code"]),
                (row["centre_name"],),
                line,
                "centre",
                errors,
                label=f"{row['centre_code']} in ward {row['ward_code']}",
            )
    if errors:
        raise ImportRefused(errors)

    report = ImportReport(kind="boundaries", rows=len(rows))
    have_counties = {c.code: c for c in await session.scalars(select(County))}
    have_constituencies = {c.code: c for c in await session.scalars(select(Constituency))}
    have_wards = {w.code: w for w in await session.scalars(select(Ward))}
    ward_code_of = {w.id: w.code for w in have_wards.values()}
    have_centres = {
        (ward_code_of.get(c.ward_id, ""), c.code): c
        for c in await session.scalars(select(RegistrationCentre))
    }

    def note(level: str, code: str, change: str, detail: str = "") -> None:
        report.changes.append(Change(level, code, change, detail))

    def upsert(level: str, label: str, found, model: type, values: dict, parent=None):  # type: ignore[no-untyped-def]
        """Create the place from `values`, or rename it, move it under `parent` (its field, id,
        level and code) and restore it; each change is noted."""
        name = values["name"]
        if found is None:
            found = model(**values)
            session.add(found)
            note(level, label, "created", name)
            return found
        if found.name != name:
            note(level, label, "renamed", f"{found.name} -> {name}")
            found.name = name
        if parent is not None:
            field, parent_id, parent_level, parent_code = parent
            if getattr(found, field) != parent_id:
                note(level, label, "moved", f"to {parent_level} {parent_code}")
                setattr(found, field, parent_id)
        if found.retired:
            found.retired = False
            note(level, label, "restored", found.name)
        return found

    def retire(level: str, label: str, found) -> None:  # type: ignore[no-untyped-def]
        if not found.retired:
            found.retired = True
            note(level, label, "retired", found.name)

    for code, ((name,), _) in counties.items():
        have_counties[code] = upsert(
            "county", code, have_counties.get(code), County, {"code": code, "name": name}
        )
    await session.flush()

    for code, ((name, county_code), _) in constituencies.items():
        parent = have_counties[county_code]
        have_constituencies[code] = upsert(
            "constituency",
            code,
            have_constituencies.get(code),
            Constituency,
            {"code": code, "name": name, "county_id": parent.id},
            ("county_id", parent.id, "county", county_code),
        )
    await session.flush()

    for code, ((name, constituency_code), _) in wards.items():
        parent = have_constituencies[constituency_code]
        have_wards[code] = upsert(
            "ward",
            code,
            have_wards.get(code),
            Ward,
            {"code": code, "name": name, "constituency_id": parent.id},
            ("constituency_id", parent.id, "constituency", constituency_code),
        )
    await session.flush()

    for (ward_code, code), ((name,), _) in centres.items():
        upsert(
            "centre",
            f"{ward_code}/{code}",
            have_centres.get((ward_code, code)),
            RegistrationCentre,
            {"code": code, "name": name, "ward_id": have_wards[ward_code].id},
        )

    covered = {have_counties[code].id for code in counties}
    county_of_constituency = {c.id: c.county_id for c in have_constituencies.values()}
    for code, found in have_constituencies.items():
        if found.county_id in covered and code not in constituencies:
            retire("constituency", code, found)
    for code, found in have_wards.items():
        if county_of_constituency.get(found.constituency_id) in covered and code not in wards:
            retire("ward", code, found)
    listed = {ward_code for ward_code, _ in centres}
    for (ward_code, code), found in have_centres.items():
        if ward_code in listed and (ward_code, code) not in centres:
            retire("centre", f"{ward_code}/{code}", found)

    return await _finish(session, report, text, filename, actor, dry_run)


# Register


def _count(value: str, line: int, name: str, errors: list[str]) -> int | None:
    if not value:
        return None
    try:
        number = int(value.replace(",", ""))
    except ValueError:
        errors.append(f"Line {line}: {name} is not a whole number.")
        return None
    if number < 0:
        errors.append(f"Line {line}: {name} is negative.")
    return number


def _percent(value: str, line: int, errors: list[str]) -> Decimal | None:
    if not value:
        return None
    try:
        number = Decimal(value.rstrip("%"))
        if not number.is_finite():
            raise InvalidOperation
        number = number.quantize(Decimal("0.01"))
    except InvalidOperation:
        errors.append(f"Line {line}: turnout_pct is not a number.")
        return None
    if not Decimal(0) <= number <= Decimal(100):
        errors.append(f"Line {line}: turnout_pct is outside 0 to 100.")
    return number


async def import_register(
    session: AsyncSession,
    text: str,
    *,
    filename: str = "",
    actor: User | None,
    dry_run: bool = False,
) -> ImportReport:
    """Set registered voters per county, ward and centre, and turnout per county.

    A row with a ward and centre code is a centre, a ward code alone a ward, and a county code
    alone a county. Targets keep their numbers until a manager refreshes them.
    """
    rows = _read(text, REGISTER_COLUMNS)
    have_counties = {c.code: c for c in await session.scalars(select(County))}
    have_wards = {w.code: w for w in await session.scalars(select(Ward))}
    ward_code_of = {w.id: w.code for w in have_wards.values()}
    have_centres = {
        (ward_code_of.get(c.ward_id, ""), c.code): c
        for c in await session.scalars(select(RegistrationCentre))
    }
    errors: list[str] = []
    seen: dict[tuple, int] = {}
    planned: list[tuple[str, str, object, int | None, Decimal | None]] = []
    for line, row in enumerate(rows, start=2):
        voters = _count(row["registered_voters"], line, "registered_voters", errors)
        turnout = _percent(row["turnout_pct"], line, errors)
        ward_code, centre_code, county_code = (
            row["ward_code"],
            row["centre_code"],
            row["county_code"],
        )
        if centre_code and ward_code:
            level, key, target = (
                "centre",
                (ward_code, centre_code),
                have_centres.get((ward_code, centre_code)),
            )
            label = f"{ward_code}/{centre_code}"
        elif ward_code and not centre_code:
            level, key, target, label = "ward", ward_code, have_wards.get(ward_code), ward_code
        elif county_code and not centre_code:
            level, key, target, label = (
                "county",
                county_code,
                have_counties.get(county_code),
                county_code,
            )
        else:
            errors.append(
                f"Line {line}: give a county_code, a ward_code, or a ward_code and centre_code."
            )
            continue
        if target is None:
            errors.append(f"Line {line}: no {level} with code {label}.")
            continue
        if (level, key) in seen:
            errors.append(f"Line {line}: {level} {label} is also on line {seen[(level, key)]}.")
            continue
        seen[(level, key)] = line
        if level != "county" and turnout is not None:
            errors.append(f"Line {line}: turnout_pct is kept per county only.")
            continue
        if voters is None and turnout is None:
            errors.append(f"Line {line}: nothing to set.")
            continue
        planned.append((level, label, target, voters, turnout))
    if errors:
        raise ImportRefused(errors)

    report = ImportReport(kind="register", rows=len(rows))
    for level, label, target, voters, turnout in planned:
        if voters is not None and target.registered_voters != voters:
            report.changes.append(
                Change(level, label, "voters", f"{target.registered_voters} -> {voters}")
            )
            target.registered_voters = voters
        if turnout is not None and target.turnout_2022_pct != turnout:
            report.changes.append(
                Change(level, label, "turnout", f"{target.turnout_2022_pct} -> {turnout}")
            )
            target.turnout_2022_pct = turnout
    return await _finish(session, report, text, filename, actor, dry_run)


async def _finish(
    session: AsyncSession,
    report: ImportReport,
    text: str,
    filename: str,
    actor: User | None,
    dry_run: bool,
) -> ImportReport:
    """Commit with its report rows and audit entry, or roll back a dry run."""
    if dry_run:
        await session.rollback()
        return report
    run = ImportRun(
        kind=report.kind,
        filename=filename[:255],
        sha256=sha256_hex(text),
        rows=report.rows,
        counts=report.counts,
        actor_id=actor.id if actor is not None else None,
    )
    session.add(run)
    await session.flush()
    session.add_all(_change_rows(run, report.changes))
    record(
        session,
        actor=actor,
        action=f"import.{report.kind}",
        subject_type="import_run",
        subject_id=run.id,
        detail={"file": filename[:255], "rows": report.rows, "changes": report.counts},
    )
    await session.commit()
    report.applied = True
    return report


def _change_rows(run: ImportRun, changes: Iterable[Change]) -> list[ImportChange]:
    return [
        ImportChange(run_id=run.id, level=c.level, code=c.code, change=c.change, detail=c.detail)
        for c in changes
    ]
