"""The app starts, serves, and keeps every data route under /api."""

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from backend.config import get_settings
from backend.main import app, create_app


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


async def test_every_route_but_health_is_under_the_api_prefix() -> None:
    """Read in the process: the schema is not served at all outside development."""
    paths = set(app.openapi()["paths"])

    assert "/health" in paths
    assert {p for p in paths if p != "/health"} == {p for p in paths if p.startswith("/api/")}


async def test_cors_headers_are_sent_for_the_vite_dev_server(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


# ------------------------------------------------------ serving the built SPA


async def test_no_static_dir_serves_the_api_alone(client: httpx.AsyncClient) -> None:
    """Dev runs the SPA on Vite, so nothing is mounted at /."""
    assert (await client.get("/")).status_code == 404


async def test_a_built_spa_is_served_at_the_root(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<h1>war room</h1>", encoding="utf-8")
    (tmp_path / "app.js").write_text("// bundle", encoding="utf-8")

    async for built in _client_with_static(tmp_path):
        index = await built.get("/")
        assert index.status_code == 200
        assert "war room" in index.text
        assert (await built.get("/app.js")).status_code == 200


async def test_the_spa_does_not_shadow_the_api_or_the_docs(tmp_path: Path) -> None:
    """The mount is last, so /api and /health still answer."""
    (tmp_path / "index.html").write_text("<h1>war room</h1>", encoding="utf-8")

    async for built in _client_with_static(tmp_path):
        assert (await built.get("/health")).json()["status"] == "ok"
        assert (await built.get("/api/campaigns/")).status_code == 401


async def test_a_missing_static_dir_fails_at_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Better than booting and serving 404s for the whole app."""
    monkeypatch.setenv("STATIC_DIR", str(Path("no", "such", "build")))
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="not a directory"):
            create_app()
    finally:
        get_settings.cache_clear()


# --------------------------------------------------- what a deploy serves


async def _built(monkeypatch: pytest.MonkeyPatch, *, debug: str) -> httpx.AsyncClient:
    monkeypatch.setenv("DEBUG", debug)
    get_settings.cache_clear()
    built = create_app()
    return built


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
async def test_the_interactive_docs_are_a_development_tool(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    """They describe every route and field, so a deploy does not serve them."""
    try:
        on = await _built(monkeypatch, debug="true")
        transport = httpx.ASGITransport(app=on)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            assert (await client.get(path)).status_code == 200, f"{path} in development"

        off = await _built(monkeypatch, debug="false")
        transport = httpx.ASGITransport(app=off)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            assert (await client.get(path)).status_code == 404, f"{path} on a deploy"
    finally:
        get_settings.cache_clear()


async def test_the_schema_is_still_built_in_the_process_with_the_docs_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The contract checks read it this way, so closing the route must not close it."""
    try:
        off = await _built(monkeypatch, debug="false")
        paths = off.openapi()["paths"]
    finally:
        get_settings.cache_clear()

    assert "/api/campaigns/" in paths
    assert len(paths) > 20


async def test_a_deploy_does_not_answer_the_route_the_docs_are_built_from(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """With the SPA mounted at "/", an unknown path must not fall through to it."""
    (tmp_path / "index.html").write_text("<h1>war room</h1>", encoding="utf-8")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("STATIC_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        built = create_app()
        transport = httpx.ASGITransport(app=built)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            served = await client.get("/openapi.json")
            # The SPA answers it, and what it answers is not the schema.
            assert "paths" not in served.text
            assert (await client.get("/api/campaigns/")).status_code == 401
    finally:
        get_settings.cache_clear()
