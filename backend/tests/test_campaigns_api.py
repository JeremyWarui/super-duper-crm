"""Reading campaigns, and the refusals when the console sets one up."""

import uuid

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Campaign
from tests.conftest import World
from tests.factories import make_rival_campaign


def _setup_body(world: World, **overrides) -> dict:
    body = {
        "title": "Peter for Kasarani",
        "seat": "mp",
        "constituency": str(world.constituency.id),
        "aspirant": {"username": "peter"},
    }
    return {**body, **overrides}


@pytest.mark.parametrize("role", ["candidate", "manager", "mobilizer"])
async def test_everyone_on_a_campaign_sees_it_and_not_a_rival_s(
    client: httpx.AsyncClient, session: AsyncSession, world: World, role: str
) -> None:
    rival = await make_rival_campaign(session, world.other_ward)

    body = (await client.get("/api/campaigns/", headers=world.headers(role))).json()
    other = await client.get(f"/api/campaigns/{rival.id}/", headers=world.headers(role))

    assert [c["title"] for c in body] == ["Jane for Roysambu"]
    assert other.status_code == 404


async def test_setting_up_a_campaign_in_an_area_that_does_not_exist_is_refused(
    client: httpx.AsyncClient, world: World, admin_headers: dict
) -> None:
    response = await client.post(
        "/api/admin/campaigns/",
        headers=admin_headers,
        json=_setup_body(world, constituency=str(uuid.uuid4())),
    )

    assert (response.status_code, response.json()["detail"]) == (400, "No such constituency.")


async def test_an_mca_seat_needs_its_ward_s_registration_centres_loaded(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    response = await client.post(
        "/api/admin/campaigns/",
        headers=admin_headers,
        json=_setup_body(
            world, title="Peter for Githurai", seat="mca", ward=str(world.other_ward.id)
        ),
    )

    assert (response.status_code, response.json()["detail"]) == (
        400,
        "That ward has no registration centres loaded; load the geography first.",
    )
    assert (
        await session.scalar(select(Campaign).where(Campaign.title == "Peter for Githurai")) is None
    )


@pytest.mark.parametrize("path", ["/api/campaigns/setup/", "/api/auth/register/"])
async def test_nobody_signs_up_or_sets_up_a_campaign_for_themselves(
    client: httpx.AsyncClient, world: World, path: str
) -> None:
    response = await client.post(
        path,
        headers=world.headers("manager"),
        json={**_setup_body(world), "username": "walkin", "password": "a-long-password"},
    )

    assert response.status_code in (404, 405)
