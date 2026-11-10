"""Running the installation: health, a data export, backups and restores, and test sends."""

import asyncio
import csv
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from alembic.script import ScriptDirectory
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from backend import __version__
from backend.config import get_settings
from backend.models import BackupRun, Base, Campaign, OrganisationType, User, WorkspaceKind
from backend.services import texting
from backend.services.audit import record
from backend.services.errors import Refused
from backend.services.payouts import get_payout_provider
from backend.services.setup import services
from backend.services.sms import require_phone

ALEMBIC_DIR = Path(__file__).resolve().parents[3] / "alembic"
# Sign-in secrets: an export is for records and moving providers, and must not open accounts.
SECRET_TABLES = {"auth_tokens", "login_invites", "setup_tokens"}
SECRET_COLUMNS = {"users": {"password_hash"}}
ARCHIVE = re.compile(r"^backup-(\d{8})-(\d{6})\.tar\.gz$")
KEEP_DAILY = 14
KEEP_WEEKLY = 8
CONFIRM = "--yes-erase-current-data"


# Health


def migration_head() -> str | None:
    try:
        return ScriptDirectory(str(ALEMBIC_DIR)).get_current_head()
    except Exception:
        return None


def _disk(label: str, folder: str) -> dict:
    path = Path(folder).resolve()
    probe = path
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    usage = shutil.disk_usage(probe)
    return {"label": label, "path": str(path), "free_bytes": usage.free, "total_bytes": usage.total}


async def health(session: AsyncSession, organisation_type: OrganisationType | None) -> dict:
    """What the console's Health tab shows; a service that is not set up is reported, not raised."""
    settings = get_settings()
    database: dict = {"reachable": True, "detail": "", "size_bytes": None}
    current = None
    try:
        await session.execute(text("SELECT 1"))
        try:
            async with session.begin_nested():
                current = await session.scalar(text("SELECT version_num FROM alembic_version"))
        except Exception:
            current = None
        if session.bind.dialect.name == "postgresql":
            database["size_bytes"] = await session.scalar(
                text("SELECT pg_database_size(current_database())")
            )
    except Exception as exc:
        await session.rollback()
        database = {
            "reachable": False,
            "detail": str(exc).splitlines()[0][:300],
            "size_bytes": None,
        }
    head = migration_head()
    states = [
        {"key": s.key, "label": s.label, "mode": s.mode, "configured": s.live} for s in services()
    ]
    last = None
    if database["reachable"]:
        run = await session.scalar(select(BackupRun).order_by(BackupRun.created_at.desc()).limit(1))
        if run is not None:
            last = {
                "at": run.finished_at or run.created_at,
                "status": run.status,
                "path": run.path,
                "size": run.size,
                "detail": run.detail,
            }
    return {
        "version": __version__,
        "migration": {
            "current": current,
            "head": head,
            "up_to_date": bool(head) and current == head,
        },
        "database": database,
        "organisation_type": organisation_type.value if organisation_type else None,
        "services": states,
        "last_backup": last,
        "disks": [_disk("Uploads", settings.upload_dir), _disk("Backups", settings.backup_dir)],
    }


# Export


def _plain(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (uuid.UUID, Decimal)):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    return value


def exported_tables() -> list[str]:
    return [t.name for t in Base.metadata.sorted_tables if t.name not in SECRET_TABLES]


async def export_archive(
    session: AsyncSession, *, actor: User | None, organisation_type: OrganisationType | None
) -> tuple[str, bytes]:
    """Every table but sign-in secrets, as JSON and CSV in one zip; audited.

    A party copy leaves out the supporters of hosted workspaces, which belong to their aspirants.
    """
    created = datetime.now(UTC)
    party = organisation_type == OrganisationType.PARTY
    counts: dict[str, int] = {}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for table in Base.metadata.sorted_tables:
            if table.name in SECRET_TABLES:
                continue
            hidden = SECRET_COLUMNS.get(table.name, set())
            columns = [c for c in table.columns if c.name not in hidden]
            query = select(*columns)
            if party and table.name == "supporters":
                query = query.where(
                    table.c.campaign_id.in_(
                        select(Campaign.id).where(Campaign.kind != WorkspaceKind.HOSTED)
                    )
                )
            rows = [
                {c.name: _plain(v) for c, v in zip(columns, row, strict=True)}
                for row in (await session.execute(query)).all()
            ]
            counts[table.name] = len(rows)
            archive.writestr(
                f"json/{table.name}.json", json.dumps(rows, ensure_ascii=False, indent=1)
            )
            out = io.StringIO()
            writer = csv.DictWriter(out, fieldnames=[c.name for c in columns])
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in row.items()}
                )
            archive.writestr(f"csv/{table.name}.csv", out.getvalue())
        manifest = {
            "created_at": created.isoformat(),
            "version": __version__,
            "migration": migration_head(),
            "organisation_type": organisation_type.value if organisation_type else None,
            "tables": counts,
            "left_out": sorted(SECRET_TABLES)
            + ["users.password_hash"]
            + (["supporters of hosted workspaces"] if party else []),
        }
        archive.writestr("manifest.json", json.dumps(manifest, indent=1))
    record(
        session,
        actor=actor,
        action="ops.export",
        subject_type="installation",
        detail={"tables": len(counts), "rows": sum(counts.values())},
    )
    await session.commit()
    return f"export-{created:%Y%m%d-%H%M%S}.zip", buffer.getvalue()


# Backup and restore


@dataclass
class Database:
    host: str
    port: str
    user: str
    password: str
    name: str

    @property
    def args(self) -> list[str]:
        return ["-h", self.host, "-p", self.port, "-U", self.user, "-d", self.name]

    @property
    def env(self) -> dict[str, str]:
        return {**os.environ, "PGPASSWORD": self.password}


def _database() -> Database:
    url = make_url(get_settings().database_url)
    if not url.drivername.startswith("postgresql"):
        raise Refused("Backups and restores need the Postgres database.")
    return Database(
        host=url.host or "localhost",
        port=str(url.port or 5432),
        user=url.username or "postgres",
        password=url.password or "",
        name=url.database or "",
    )


def _tool(name: str) -> str:
    folder = get_settings().pg_bin_dir
    found = shutil.which(name, path=folder) if folder else shutil.which(name)
    if found is None:
        raise Refused(f"{name} was not found; install the Postgres client or set PG_BIN_DIR.")
    return found


def _run(command: list[str], env: dict[str, str]) -> None:
    done = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise Refused(
            f"{Path(command[0]).stem} failed: {(done.stderr or done.stdout).strip()[:500]}"
        )


def _write_backup(folder: Path, stamp: datetime) -> Path:
    db = _database()
    folder.mkdir(parents=True, exist_ok=True)
    final = folder / f"backup-{stamp:%Y%m%d-%H%M%S}.tar.gz"
    with tempfile.TemporaryDirectory() as work:
        dump = Path(work) / "database.dump"
        _run([_tool("pg_dump"), "-Fc", "--no-owner", "-f", str(dump), *db.args], db.env)
        partial = final.with_suffix(".part")
        with tarfile.open(partial, "w:gz") as archive:
            archive.add(dump, arcname="database.dump")
            uploads = Path(get_settings().upload_dir)
            if uploads.is_dir():
                archive.add(uploads, arcname="uploads")
            manifest = json.dumps(
                {
                    "created_at": stamp.isoformat(),
                    "version": __version__,
                    "migration": migration_head(),
                }
            ).encode()
            info = tarfile.TarInfo("manifest.json")
            info.size = len(manifest)
            archive.addfile(info, io.BytesIO(manifest))
        partial.replace(final)
    return final


def kept(names: list[str]) -> set[str]:
    """The archives to keep: the newest on each of the 14 latest days that have one, and the
    newest in each of the 8 latest weeks."""
    dated = sorted(
        (
            (datetime.strptime(m[1] + m[2], "%Y%m%d%H%M%S"), name)
            for name in names
            if (m := ARCHIVE.match(name))
        ),
        reverse=True,
    )
    days: dict[date, str] = {}
    weeks: dict[tuple[int, int], str] = {}
    for when, name in dated:
        days.setdefault(when.date(), name)
        weeks.setdefault(when.isocalendar()[:2], name)
    newest_days = sorted(days, reverse=True)[:KEEP_DAILY]
    newest_weeks = sorted(weeks, reverse=True)[:KEEP_WEEKLY]
    # Every archive of the newest day stays, so a backup taken before a restore never
    # removes the one being restored.
    latest = {name for when, name in dated if when.date() == dated[0][0].date()}
    return {days[d] for d in newest_days} | {weeks[w] for w in newest_weeks} | latest


def prune(folder: Path) -> list[str]:
    # Only archives this command wrote; a renamed or copied file is never touched.
    names = [p.name for p in folder.glob("backup-*.tar.gz") if ARCHIVE.match(p.name)]
    keep = kept(names)
    gone = sorted(n for n in names if n not in keep)
    for name in gone:
        (folder / name).unlink(missing_ok=True)
    return gone


async def backup(session: AsyncSession) -> BackupRun:
    """Dump the database and the uploads into one archive, prune old ones, and log the run."""
    folder = Path(get_settings().backup_dir)
    run = BackupRun(status="running")
    session.add(run)
    await session.commit()
    try:
        path = await asyncio.to_thread(_write_backup, folder, datetime.now(UTC))
        gone = await asyncio.to_thread(prune, folder)
        run.status, run.path, run.size = "ok", str(path.resolve()), path.stat().st_size
        run.detail = f"Removed {len(gone)} older archive(s)." if gone else ""
    except Exception as exc:
        run.status, run.detail = "failed", str(exc)[:1000]
    run.finished_at = datetime.now(UTC)
    record(
        session,
        actor=None,
        action="ops.backup",
        subject_type="backup_run",
        subject_id=run.id,
        detail={"status": run.status, "size": run.size},
    )
    await session.commit()
    return run


def restore(path: Path, *, confirmed: bool) -> str:
    """Replace the database and uploads with an archive's. Refused without the confirmation."""
    if not confirmed:
        raise Refused(
            f"Restoring erases the current data. Run it again with {CONFIRM} to go ahead."
        )
    if not path.is_file():
        raise Refused(f"No archive at {path}.")
    db = _database()
    with tempfile.TemporaryDirectory() as work:
        unpack(path, Path(work))
        dump = Path(work) / "database.dump"
        if not dump.is_file():
            raise Refused("That archive has no database.dump; it is not a backup.")
        _run(
            [
                _tool("pg_restore"),
                "--clean",
                "--if-exists",
                "--no-owner",
                "--single-transaction",
                *db.args,
                str(dump),
            ],
            db.env,
        )
        restored = Path(work) / "uploads"
        if restored.is_dir():
            settings = get_settings()
            try:
                replace_uploads(
                    restored, Path(settings.upload_dir), keep_in=Path(settings.backup_dir)
                )
            except OSError as failed:
                raise Refused(
                    f"The database was restored, but the uploaded files were not: {failed}. "
                    "Fix the cause and run the restore again."
                ) from failed
    return "Restored. Restart the app so it reads the restored data."


def unpack(path: Path, into: Path) -> None:
    """Extract an archive; refused, with nothing changed, when it cannot be read."""
    try:
        with tarfile.open(path, "r:gz") as archive:
            archive.extractall(into, filter="data")
    except (OSError, EOFError, tarfile.TarError) as failed:
        raise Refused(f"That archive could not be read: {failed}. Nothing was changed.") from failed


def replace_uploads(restored: Path, uploads: Path, *, keep_in: Path) -> Path | None:
    """Put the archive's uploads in place, first copying the current ones into `keep_in`.

    Swaps the folder's contents, never the folder, which may be a mounted volume. Returns
    where the old uploads were kept, if there were any.
    """
    kept = None
    if uploads.exists():
        kept = keep_in / f"uploads.before-restore-{datetime.now():%Y%m%d-%H%M%S}"
        shutil.copytree(uploads, kept)
        for child in uploads.iterdir():
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()
    shutil.copytree(restored, uploads, dirs_exist_ok=True)
    return kept


# Test sends


async def test_sms(session: AsyncSession, phone: str, *, actor: User) -> str:
    number = require_phone(phone, "That is not a phone number.")
    result = await texting.send_test(session, number, actor=actor)
    record(
        session,
        actor=actor,
        action="ops.test_sms",
        subject_type="installation",
        detail={"delivered": result.delivered},
    )
    await session.commit()
    return texting.test_outcome(
        result, number, "SMS is not configured: the text was recorded, not sent."
    )


async def test_payout(session: AsyncSession, phone: str, *, actor: User) -> str:
    """A practice payout of KES 1; refused where payouts move real money."""
    provider = get_payout_provider()
    if provider.moves_money:
        raise Refused("Payouts are live here and move real money; check them with a real payment.")
    number = require_phone(phone, "That is not a phone number.")
    test_id = uuid.uuid4()
    result = await provider.send(
        payment_id=test_id,
        reference=f"TEST-{test_id.hex[:12]}",
        phone=number,
        name="Test payout",
        amount_kes=1,
    )
    record(
        session,
        actor=actor,
        action="ops.test_payout",
        subject_type="installation",
        detail={"status": result.status.value},
    )
    await session.commit()
    return f"Practice payout {result.status.value} under {result.reference}; no money moved."
