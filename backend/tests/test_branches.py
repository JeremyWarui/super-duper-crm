"""County branches: the superuser writes them, the public site shows only published ones."""

from datetime import date

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Branch, County
from backend.seed.site import seed_branches
from tests.conftest import World

pytestmark = pytest.mark.party_only

BRANCH = {
    "chairperson": "Wanjiru Kamau",
    "secretary": "Otieno Ouma",
    "office_address": "Moi Avenue, Nairobi",
    "phone": "0700 111222",
    "email": "nairobi@example.com",
    "next_meeting_on": "2026-11-20",
    "next_meeting_venue": "Branch office",
}


async def test_only_the_superuser_writes_a_branch(
    client: httpx.AsyncClient, world: World, admin_headers: dict
) -> None:
    path = f"/api/admin/party/branches/{world.county.id}/"
    refused = await client.put(path, headers=world.headers("manager"), json=BRANCH)
    saved = await client.put(path, headers=admin_headers, json={**BRANCH, "published": True})

    assert refused.status_code == 403
    assert saved.status_code == 200, saved.text
    assert saved.json()["chairperson"] == "Wanjiru Kamau"


async def test_an_unpublished_branch_is_not_public(
    client: httpx.AsyncClient, world: World, admin_headers: dict
) -> None:
    path = f"/api/admin/party/branches/{world.county.id}/"
    await client.put(path, headers=admin_headers, json=BRANCH)

    assert (await client.get("/api/party/branches/")).json() == []
    assert (await client.get(f"/api/party/branches/{world.county.id}/")).status_code == 404

    await client.put(path, headers=admin_headers, json={**BRANCH, "published": True})
    shown = await client.get(f"/api/party/branches/{world.county.id}/")

    assert shown.status_code == 200
    assert shown.json()["constituencies"][0]["name"] == world.constituency.name
    assert {w["name"] for w in shown.json()["constituencies"][0]["wards"]} >= {world.ward.name}


async def test_the_seed_gives_each_county_one_branch(session: AsyncSession, world: World) -> None:
    session.add(County(name="Mombasa", code="001"))
    await session.commit()

    first = await seed_branches(session, date(2026, 11, 1))
    again = await seed_branches(session, date(2026, 11, 1))

    counties = await session.scalar(select(func.count()).select_from(County))
    assert first == counties and again == 0
    assert await session.scalar(select(func.count()).select_from(Branch)) == counties
