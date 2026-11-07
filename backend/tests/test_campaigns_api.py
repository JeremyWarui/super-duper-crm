"""Reading campaigns, and the refusals when one is built."""

import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Seat
from backend.services.campaigns import build_campaign
from backend.services.errors import Refused
from tests.conftest import World
from tests.factories import fresh_password, make_rival_campaign


@pytest.mark.parametrize("role", ["candidate", "manager", "mobilizer"])
async def test_everyone_on_a_campaign_sees_it_and_not_a_rival_s(
    client: httpx.AsyncClient, session: AsyncSession, world: World, role: str
) -> None:
    rival = await make_rival_campaign(session, world.other_ward)

    body = (await client.get("/api/campaigns/", headers=world.headers(role))).json()
    other = await client.get(f"/api/campaigns/{rival.id}/", headers=world.headers(role))

    assert [c["title"] for c in body] == ["Jane for Roysambu"]
    assert other.status_code == 404


async def test_a_campaign_in_an_area_that_does_not_exist_is_refused(
    session: AsyncSession, world: World
) -> None:
    with pytest.raises(Refused, match="No such constituency."):
        await build_campaign(
            session, title="Peter for Kasarani", seat=Seat.MP, constituency=uuid.uuid4()
        )


async def test_an_mca_seat_needs_its_ward_s_registration_centres_loaded(
    session: AsyncSession, world: World
) -> None:
    with pytest.raises(Refused, match="no registration centres loaded"):
        await build_campaign(
            session, title="Peter for Githurai", seat=Seat.MCA, ward=world.other_ward.id
        )


@pytest.mark.parametrize("path", ["/api/campaigns/setup/", "/api/auth/register/"])
async def test_nobody_signs_up_or_sets_up_a_campaign_for_themselves(
    client: httpx.AsyncClient, world: World, path: str
) -> None:
    response = await client.post(
        path,
        headers=world.headers("manager"),
        json={
            "title": "Peter for Kasarani",
            "seat": "mp",
            "constituency": str(world.constituency.id),
            "username": "walkin",
            "password": fresh_password(),
        },
    )

    assert response.status_code in (404, 405)
