"""The site and party settings: public to read, a superuser's to change."""

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    AuditEvent,
    OrganisationType,
    PartyConsentChannel,
    PartySettings,
    SiteSettings,
)
from backend.services.consent import PARTY_WORDING
from tests.conftest import World
from tests.factories import site_settings

CHANGE = {
    "name": "Umoja Party",
    "primary_colour": "#0A7B3E",
    "secondary_colour": "#ffd700",
    "social_links": {"x": "https://x.com/umoja"},
}


@pytest.fixture(autouse=True)
async def settings_rows(session: AsyncSession, organisation_type: OrganisationType) -> None:
    session.add_all(
        [
            site_settings(organisation_type=organisation_type),
            PartySettings(registration_number="PP-1"),
        ]
    )
    await session.commit()


async def test_anyone_reads_the_site_and_party_settings_without_a_login(
    client: httpx.AsyncClient, organisation_type: OrganisationType
) -> None:
    site = await client.get("/api/site/")
    party = await client.get("/api/party/")

    assert site.status_code == 200
    assert site.json()["organisation_type"] == organisation_type
    assert site.json()["name"] == "Party name"
    assert site.json()["primary_colour"] == "#1f2937"
    if organisation_type is OrganisationType.ASPIRANT:
        assert party.status_code == 404
        return
    assert party.json()["registration_number"] == "PP-1"
    assert party.json()["consent_wording"] == PARTY_WORDING[PartyConsentChannel.WEB_FORM]
    assert "name" not in party.json()


async def test_only_a_superuser_changes_them_and_the_change_is_audited(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    admin_headers: dict,
    organisation_type: OrganisationType,
) -> None:
    party_install = organisation_type is OrganisationType.PARTY
    refused = await client.put("/api/admin/site/", headers=world.headers("manager"), json=CHANGE)
    badly = await client.put(
        "/api/admin/site/", headers=admin_headers, json={**CHANGE, "primary_colour": "green"}
    )
    saved = await client.put("/api/admin/site/", headers=admin_headers, json=CHANGE)
    party = await client.put(
        "/api/admin/party/", headers=admin_headers, json={"founded_year": "2024"}
    )

    assert refused.status_code == 403
    assert badly.status_code == 400
    assert saved.status_code == 200, saved.text
    assert party.status_code == (200 if party_install else 404), party.text
    assert (await client.get("/api/site/")).json()["primary_colour"] == "#0a7b3e"
    events = {
        e.action: e.detail
        for e in await session.scalars(
            select(AuditEvent).where(AuditEvent.action.like("%_settings.update"))
        )
    }
    assert events.pop("site_settings.update") == {
        "fields": ["name", "primary_colour", "secondary_colour", "social_links"]
    }
    if party_install:
        assert (await client.get("/api/party/")).json()["founded_year"] == "2024"
        assert events == {
            "party_settings.update": {"fields": ["founded_year", "registration_number"]}
        }
    else:
        assert events == {}


async def test_the_organisation_type_cannot_be_changed_through_the_api(
    client: httpx.AsyncClient,
    session: AsyncSession,
    admin_headers: dict,
    organisation_type: OrganisationType,
) -> None:
    other = next(kind for kind in OrganisationType if kind is not organisation_type)
    response = await client.put(
        "/api/admin/site/", headers=admin_headers, json={**CHANGE, "organisation_type": other}
    )

    assert response.status_code == 400
    session.expire_all()
    assert (await session.get(SiteSettings, 1)).organisation_type == organisation_type


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
