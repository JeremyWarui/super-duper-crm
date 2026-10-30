"""The party's settings: public to read, a superuser's to change."""

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AuditEvent, PartySettings
from tests.conftest import World

CHANGE = {
    "name": "Umoja Party",
    "primary_colour": "#0A7B3E",
    "secondary_colour": "#ffd700",
    "social_links": {"x": "https://x.com/umoja"},
}


@pytest.fixture(autouse=True)
async def settings_row(session: AsyncSession) -> None:
    session.add(PartySettings(name="Party name"))
    await session.commit()


async def test_anyone_reads_the_party_settings_without_a_login(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/party/")

    assert response.status_code == 200
    assert response.json()["name"] == "Party name"
    assert response.json()["primary_colour"] == "#1f2937"


async def test_only_a_superuser_changes_them_and_the_change_is_audited(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    refused = await client.put("/api/admin/party/", headers=world.headers("manager"), json=CHANGE)
    badly = await client.put(
        "/api/admin/party/", headers=admin_headers, json={**CHANGE, "primary_colour": "green"}
    )
    saved = await client.put("/api/admin/party/", headers=admin_headers, json=CHANGE)

    assert refused.status_code == 403
    assert badly.status_code == 400
    assert saved.status_code == 200, saved.text
    assert (await client.get("/api/party/")).json()["primary_colour"] == "#0a7b3e"
    event = await session.scalar(
        select(AuditEvent).where(AuditEvent.action == "party_settings.update")
    )
    assert event is not None and event.subject_id is None
    assert event.detail == {
        "fields": ["name", "primary_colour", "secondary_colour", "social_links"]
    }
