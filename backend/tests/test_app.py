"""The app starts, serves, and keeps every data route under /api."""

import httpx
import pytest

from backend.main import app


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_health(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_every_route_but_health_is_under_the_api_prefix(
    client: httpx.AsyncClient,
) -> None:
    """The frontend points VITE_API_URL at /api; a route outside it is unreachable."""
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    paths = set(response.json()["paths"])
    assert "/health" in paths
    assert {p for p in paths if p != "/health"} == {p for p in paths if p.startswith("/api/")}


async def test_cors_headers_are_sent_for_the_vite_dev_server(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
