"""The app starts, serves, keeps every data route under /api, and runs the party inbox."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.main import app, create_app
from backend.models import OrganisationType
from backend.services import site
from tests.factories import site_settings


async def _client_with_static(directory: Path) -> AsyncIterator[httpx.AsyncClient]:
    """An app built with STATIC_DIR pointed at `directory`."""
    import os

    os.environ["STATIC_DIR"] = str(directory)
    get_settings.cache_clear()
    try:
        built = create_app()
        transport = httpx.ASGITransport(app=built)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        os.environ.pop("STATIC_DIR", None)
        get_settings.cache_clear()


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_health(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_a_built_spa_is_served_at_the_root(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<h1>war room</h1>", encoding="utf-8")
    (tmp_path / "app.js").write_text("// bundle", encoding="utf-8")

    async for built in _client_with_static(tmp_path):
        index = await built.get("/")
        assert index.status_code == 200
        assert "war room" in index.text
        assert (await built.get("/app.js")).status_code == 200


async def test_the_public_sign_up_and_withdrawal_pages_open_the_spa(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<h1>war room</h1>", encoding="utf-8")

    async for built in _client_with_static(tmp_path):
        for path in ("/join/abc123", "/join/abc123/", "/withdraw/xyz789", "/withdraw/xyz789/"):
            page = await built.get(path)
            assert (path, page.status_code, "war room" in page.text) == (path, 200, True)


async def test_the_spa_does_not_shadow_the_api_or_the_docs(tmp_path: Path) -> None:
    """The mount is last, so /api and /health still answer."""
    (tmp_path / "index.html").write_text("<h1>war room</h1>", encoding="utf-8")

    async for built in _client_with_static(tmp_path):
        assert (await built.get("/health")).json()["status"] == "ok"
        assert (await built.get("/api/campaigns/")).status_code == 401


async def test_a_client_side_path_serves_the_spa_and_an_unknown_api_path_stays_json(
    tmp_path: Path,
) -> None:
    (tmp_path / "index.html").write_text("<h1>war room</h1>", encoding="utf-8")

    async for built in _client_with_static(tmp_path):
        page = await built.get("/campaign/events")
        assert (page.status_code, "war room" in page.text) == (200, True)
        missing = await built.get("/api/nope/")
        assert missing.status_code == 404
        assert "war room" not in missing.text
        assert isinstance(missing.json(), dict)
        assert (await built.get("/assets/gone.js")).status_code == 404


@pytest.mark.parametrize(
    ("kind", "runs"), [(OrganisationType.PARTY, True), (OrganisationType.ASPIRANT, False)]
)
async def test_the_party_inbox_runs_only_in_a_party_installation(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    kind: OrganisationType,
    runs: bool,
) -> None:
    from backend import main

    session.add(site_settings(organisation_type=kind))
    await session.commit()
    applied = []

    async def process_requests(_: AsyncSession) -> None:
        applied.append(True)

    @asynccontextmanager
    async def same_session() -> AsyncIterator[AsyncSession]:
        yield session

    monkeypatch.setattr(main, "get_sessionmaker", lambda: same_session)
    monkeypatch.setattr(main.membership, "process_requests", process_requests)
    site._organisation_type = None
    task = asyncio.create_task(main._apply_party_requests(0))
    try:
        await asyncio.sleep(0.05)
    finally:
        task.cancel()
        site._organisation_type = None

    assert bool(applied) is runs
