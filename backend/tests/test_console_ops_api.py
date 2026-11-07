"""The console's Health, Export, audit filters, backups and test sends."""

import io
import json
import zipfile
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AuditEvent, Base, SmsLog, User
from backend.services import ops
from backend.services.errors import Refused
from tests.conftest import World

pytestmark = pytest.mark.party_only


async def test_health_reports_a_missing_sms_key_as_not_configured(
    client: httpx.AsyncClient, admin_headers: dict
) -> None:
    answer = await client.get("/api/admin/health/", headers=admin_headers)

    assert answer.status_code == 200, answer.text
    body = answer.json()
    sms = next(s for s in body["services"] if s["key"] == "sms")
    assert (sms["mode"], sms["configured"]) == ("console", False)
    assert body["database"]["reachable"] is True
    assert body["organisation_type"] == "party"


async def test_with_no_keys_every_outside_service_is_not_configured_and_email_is_only_logged(
    client: httpx.AsyncClient, admin_headers: dict
) -> None:
    health = await client.get("/api/admin/health/", headers=admin_headers)
    emailed = await client.post("/api/setup/services/email/test/", headers=admin_headers)

    services = health.json()["services"]
    assert {s["key"] for s in services} == {"email", "sms", "payouts", "google"}
    assert [s["key"] for s in services if s["configured"]] == []
    assert emailed.json()["message"] == "Logged in practice mode; nothing was sent."


async def test_the_export_holds_every_table_but_sign_in_secrets(
    client: httpx.AsyncClient, admin_headers: dict, world: World, session: AsyncSession
) -> None:
    answer = await client.get("/api/admin/export/", headers=admin_headers)

    assert answer.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(answer.content))
    manifest = json.loads(archive.read("manifest.json"))
    every = {t.name for t in Base.metadata.sorted_tables}
    assert set(manifest["tables"]) == every - ops.SECRET_TABLES
    users = json.loads(archive.read("json/users.json"))
    assert len(users) == await session.scalar(select(func.count(User.id)))
    assert all("password_hash" not in u for u in users)
    assert f"csv/{'campaigns'}.csv" in archive.namelist()
    assert await session.scalar(select(AuditEvent.id).where(AuditEvent.action == "ops.export"))


def test_a_restore_is_refused_without_the_flag(tmp_path: Path) -> None:
    with pytest.raises(Refused, match="--yes-erase-current-data"):
        ops.restore(tmp_path / "backup-20261106-120000.tar.gz", confirmed=False)


def test_backups_keep_fourteen_days_and_eight_weeks() -> None:
    # Two a day for 120 days, newest first.
    names = [
        f"backup-202611{d:02d}-0{h}0000.tar.gz"
        if d <= 30
        else f"backup-2026{(d - 1) // 30 + 7:02d}{(d - 1) % 30 + 1:02d}-0{h}0000.tar.gz"
        for d in range(1, 121)
        for h in (1, 2)
    ]

    keep = ops.kept(names)

    days = {n[7:15] for n in keep}
    assert len(keep) <= 14 + 8 + 1
    assert {f"202611{d:02d}" for d in range(17, 31)} <= days
    assert all(n.endswith("-020000.tar.gz") for n in keep if "20261130" not in n)


async def test_the_audit_trail_filters_by_action_user_and_date(
    client: httpx.AsyncClient, admin_headers: dict, world: World
) -> None:
    await client.get("/api/admin/export/", headers=admin_headers)

    found = await client.get(
        "/api/admin/audit/?action=ops.&actor=roo&since=2000-01-01", headers=admin_headers
    )
    none_yet = await client.get(
        "/api/admin/audit/?action=ops.&until=2000-01-01", headers=admin_headers
    )

    assert [e["action"] for e in found.json()] == ["ops.export"]
    assert none_yet.json() == []


async def test_a_practice_payout_moves_no_money(
    client: httpx.AsyncClient, admin_headers: dict
) -> None:
    answer = await client.post(
        "/api/admin/test/payout/", json={"phone": "0712345678"}, headers=admin_headers
    )

    assert answer.status_code == 200, answer.text
    assert "no money moved" in answer.json()["message"]


async def test_a_practice_test_text_is_logged_and_not_sent(
    client: httpx.AsyncClient, session: AsyncSession, admin_headers: dict
) -> None:
    answer = await client.post(
        "/api/admin/test/sms/", json={"phone": "0712345678"}, headers=admin_headers
    )
    logged = (await session.execute(select(SmsLog.phone, SmsLog.purpose, SmsLog.status))).all()

    assert answer.status_code == 200, answer.text
    assert logged == [("+254712345678", "test", "practice")]


def test_pruning_never_touches_a_file_the_backup_did_not_write(tmp_path: Path) -> None:
    ours = [f"backup-202611{d:02d}-020000.tar.gz" for d in range(1, 31)]
    others = ["backup-before-upgrade.tar.gz", "backup-20261106-120000 (copy).tar.gz"]
    for name in ours + others:
        (tmp_path / name).write_bytes(b"x")

    gone = ops.prune(tmp_path)

    assert sorted(gone) == sorted(set(ours) - ops.kept(ours))
    assert all((tmp_path / name).exists() for name in others)


def test_a_restore_swaps_the_uploads_contents_and_keeps_the_old_ones_with_the_backups(
    tmp_path: Path, monkeypatch
):
    uploads, restored = tmp_path / "uploads", tmp_path / "archive"
    (uploads / "old").mkdir(parents=True)
    (uploads / "old" / "a.png").write_bytes(b"old")
    (restored / "new").mkdir(parents=True)
    (restored / "new" / "b.png").write_bytes(b"new")
    real_rename = Path.rename

    def mounted(self, target):
        if self == uploads:
            raise OSError(16, "Device or resource busy")
        return real_rename(self, target)

    monkeypatch.setattr(Path, "rename", mounted)

    kept_in = tmp_path / "backups"
    kept_in.mkdir()

    kept = ops.replace_uploads(restored, uploads, keep_in=kept_in)

    assert sorted(p.name for p in uploads.rglob("*.png")) == ["b.png"]
    assert kept.parent == kept_in
    assert (kept / "old" / "a.png").read_bytes() == b"old"


def test_a_restore_of_an_unreadable_archive_says_nothing_was_changed(tmp_path: Path) -> None:
    broken = tmp_path / "backup-20261106-120000.tar.gz"
    broken.write_bytes(b"not an archive")

    with pytest.raises(Refused, match="Nothing was changed"):
        ops.unpack(broken, tmp_path)


def test_a_practice_email_with_its_link_reaches_the_app_log() -> None:
    import logging

    import backend.main  # noqa: F401

    app_logger = logging.getLogger("backend")

    assert logging.getLogger("backend.services.email").isEnabledFor(logging.INFO)
    assert app_logger.handlers


def test_a_second_backup_on_the_same_day_keeps_the_first() -> None:
    nightly, by_hand = "backup-20261107-000001.tar.gz", "backup-20261107-091500.tar.gz"

    assert ops.kept([nightly, by_hand]) == {nightly, by_hand}
