"""Reading campaigns, setting one up, and rebuilding its targets."""

import uuid

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Campaign, Target, User
from tests.conftest import World
from tests.factories import (
    auth,
    make_rival_campaign,
    members_of,
    sign_in,
)


def _setup_body(world: World, **overrides) -> dict:
    body = {
        "title": "Peter for Kasarani",
        "seat": "mp",
        "constituency": str(world.constituency.id),
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


async def test_a_manager_sets_a_campaign_up_with_its_targets_and_a_new_aspirant(
    client: httpx.AsyncClient, session: AsyncSession, world: World, new_manager: dict
) -> None:
    """Zimmerman 30,701 and Githurai 35,899 at 60% turnout: 9,211 + 10,770."""
    response = await client.post(
        "/api/campaigns/setup/",
        headers=new_manager,
        json=_setup_body(
            world,
            election_date="2027-08-10",
            new_candidate={"username": "peter", "first_name": "Peter", "last_name": "Kimani"},
        ),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["election_date"] == "2027-08-10"
    assert body["setup"] == {
        "grain": "ward",
        "units": 2,
        "total_registered": 66_600,
        "win_number": 19_981,
        "note": None,
    }
    campaign_id = uuid.UUID(body["id"])
    assert (
        await session.scalar(
            select(func.count()).select_from(Target).where(Target.campaign_id == campaign_id)
        )
        == 2
    )
    assert await members_of(session, campaign_id) == {"peter": "candidate", "newmanager": "manager"}

    login = body["candidate_login"]
    assert login["username"] == "peter"
    assert len(login["password"]) >= 12
    assert body["candidate"] == login["id"]
    for head in (new_manager, auth(await sign_in(client, "peter", login["password"]))):
        listed = (await client.get("/api/campaigns/", headers=head)).json()
        assert [c["title"] for c in listed] == ["Peter for Kasarani"]


async def test_a_candidate_sets_their_own_campaign_up_alone(
    client: httpx.AsyncClient, session: AsyncSession, world: World, new_candidate: dict
) -> None:
    response = await client.post(
        "/api/campaigns/setup/",
        headers=new_candidate,
        json={
            "title": "Peter for Governor",
            "seat": "governor",
            "county": str(world.county.id),
        },
    )

    assert response.status_code == 201, response.text
    mine = await session.scalar(select(User.id).where(User.username == "newaspirant"))
    assert response.json()["candidate"] == str(mine)
    assert await members_of(session, uuid.UUID(response.json()["id"])) == {
        "newaspirant": "candidate"
    }


async def test_a_mobilizer_may_not_set_a_campaign_up(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post(
        "/api/campaigns/setup/", headers=world.headers("mobilizer"), json=_setup_body(world)
    )
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["manager", "candidate"])
async def test_nobody_already_on_a_campaign_sets_up_another(
    client: httpx.AsyncClient, session: AsyncSession, world: World, role: str
) -> None:
    body = {"title": "A second one", "seat": "mca", "ward": str(world.other_ward.id)}
    if role == "manager":
        body["new_candidate"] = {"username": "peter"}

    reply = await client.post("/api/campaigns/setup/", headers=world.headers(role), json=body)

    assert reply.status_code == 400
    assert reply.json()["detail"] == (
        "You are already on Jane for Roysambu; a login belongs to one campaign."
    )
    assert list(await session.scalars(select(Campaign.title))) == ["Jane for Roysambu"]
    assert await session.scalar(select(User.id).where(User.username == "peter")) is None
