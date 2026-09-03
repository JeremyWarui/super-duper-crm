"""The ASGI app boots and serves. No routers exist yet, by design."""

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


async def test_openapi_is_served_and_exposes_no_data_routes(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    assert set(response.json()["paths"]) == {"/health"}


async def test_cors_headers_are_sent_for_the_vite_dev_server(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
