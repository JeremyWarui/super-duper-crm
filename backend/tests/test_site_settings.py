"""The site settings: public to read, a superuser's to change."""

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AuditEvent
from tests.conftest import World
from tests.factories import site_settings

CHANGE = {
    "name": "Jane for Parklands",
    "primary_colour": "#0A7B3E",
    "secondary_colour": "#ffd700",
    "social_links": {"x": "https://x.com/umoja"},
}


@pytest.fixture(autouse=True)
async def settings_row(session: AsyncSession) -> None:
    session.add(site_settings())
    await session.commit()


async def test_anyone_reads_the_site_settings_without_a_login(client: httpx.AsyncClient) -> None:
    site = await client.get("/api/site/")

    assert site.status_code == 200
    assert site.json()["name"] == "Site name"
    assert site.json()["primary_colour"] == "#0b5d3b"


async def test_only_a_superuser_changes_them_and_the_change_is_audited(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    refused = await client.put("/api/admin/site/", headers=world.headers("manager"), json=CHANGE)
    badly = await client.put(
        "/api/admin/site/", headers=admin_headers, json={**CHANGE, "primary_colour": "green"}
    )
    saved = await client.put("/api/admin/site/", headers=admin_headers, json=CHANGE)

    assert refused.status_code == 403
    assert badly.status_code == 400
    assert saved.status_code == 200, saved.text
    assert (await client.get("/api/site/")).json()["primary_colour"] == "#0a7b3e"
    events = {
        e.action: e.detail
        for e in await session.scalars(
            select(AuditEvent).where(AuditEvent.action.like("%_settings.update"))
        )
    }
    assert events == {
        "site_settings.update": {
            "fields": ["name", "primary_colour", "secondary_colour", "social_links"]
        }
    }


@pytest.mark.parametrize(
    "colours", [{"primary_colour": "#ffd700"}, {"secondary_colour": "#0b5d3b"}]
)
async def test_a_colour_that_makes_its_buttons_unreadable_is_refused(
    client: httpx.AsyncClient, admin_headers: dict, colours: dict
) -> None:
    response = await client.put(
        "/api/admin/site/", headers=admin_headers, json={**CHANGE, **colours}
    )

    assert response.status_code == 400
