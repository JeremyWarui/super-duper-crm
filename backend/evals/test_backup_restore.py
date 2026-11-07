"""A real backup and restore on Postgres, with pg_dump and pg_restore: rubric 16."""

import io
from pathlib import Path

import httpx
import pytest
from PIL import Image
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from backend.config import get_settings
from backend.models import User
from backend.services import ops
from tests.conftest import POSTGRES, admin_headers, postgres_url  # noqa: F401
from tests.factories import make_user

pytestmark = pytest.mark.skipif(not POSTGRES, reason="pg_dump and pg_restore need TEST_POSTGRES=1")


@pytest.fixture
def folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    uploads, backups = tmp_path / "uploads", tmp_path / "backups"
    monkeypatch.setenv("UPLOAD_DIR", str(uploads))
    monkeypatch.setenv("BACKUP_DIR", str(backups))
    monkeypatch.setenv("DATABASE_URL", postgres_url())
    get_settings.cache_clear()
    yield uploads, backups
    get_settings.cache_clear()


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), "seagreen").save(buffer, format="PNG")
    return buffer.getvalue()


async def test_a_restore_brings_back_the_database_and_the_uploaded_image(
    client: httpx.AsyncClient,
    session: AsyncSession,
    engine: AsyncEngine,
    admin_headers: dict,  # noqa: F811
    folders: tuple[Path, Path],
) -> None:
    uploads, _ = folders
    uploaded = await client.post(
        "/api/files/",
        headers=admin_headers,
        files={"file": ("photo.png", _png(), "image/png")},
        data={"area": "leaders", "public": "true"},
    )
    assert uploaded.status_code == 201, uploaded.text
    url = uploaded.json()["url"]
    await make_user(session, username="keeper")

    run = await ops.backup(session)
    assert run.status == "ok", run.detail

    await session.execute(delete(User).where(User.username == "keeper"))
    await session.commit()
    for stored in list(uploads.rglob("*")):
        if stored.is_file():
            stored.unlink()
    assert (await client.get(url)).status_code == 404
    await session.close()
    await engine.dispose()

    ops.restore(Path(run.path), confirmed=True)

    assert await session.scalar(select(User.id).where(User.username == "keeper"))
    served = await client.get(url)
    assert served.status_code == 200
    Image.open(io.BytesIO(served.content)).verify()
