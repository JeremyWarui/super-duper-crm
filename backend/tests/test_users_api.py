"""Mobilizer logins, added and removed from inside a campaign."""

import uuid

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Mobilizer, User, UserRole
from tests.conftest import World
from tests.factories import auth, make_user, sign_in


def _mobilizer(world: World, **overrides) -> dict:
    body = {
        "username": "wanjiku",
        "role": "mobilizer",
        "first_name": "Wanjiku",
        "last_name": "Njeri",
        "campaign": str(world.campaign.id),
        "ward": str(world.other_ward.id),
    }
    return {**body, **overrides}


TEAM_ONLY = "Only a candidate or a campaign manager may add or remove people."


@pytest.mark.parametrize("caller", ["manager", "candidate"])
async def test_the_manager_or_candidate_adds_a_mobilizer_who_then_works_their_ward(
    client: httpx.AsyncClient, session: AsyncSession, world: World, caller: str
) -> None:
    response = await client.post(
        "/api/users/", headers=world.headers(caller), json=_mobilizer(world)
    )

    assert response.status_code == 201, response.text
    created = response.json()
    assert created["role"] == "mobilizer"
    assert created["ward_name"] == "Githurai"
    assert len(created["password"]) >= 12
    profile = await session.get(Mobilizer, uuid.UUID(created["mobilizer"]))
    assert (profile.ward_id, profile.full_name) == (world.other_ward.id, "Wanjiku Njeri")
    stored = await session.scalar(select(User).where(User.username == "wanjiku"))
    assert created["password"] not in stored.password_hash

    head = auth(await sign_in(client, "wanjiku", created["password"]))
    listed = (await client.get("/api/campaigns/", headers=head)).json()
    assert [c["id"] for c in listed] == [str(world.campaign.id)]
    wards = (await client.get("/api/wards/", headers=head)).json()
    assert [w["name"] for w in wards] == ["Githurai"]
    still = (await client.get("/api/campaigns/", headers=world.headers(caller))).json()
    assert [c["id"] for c in still] == [str(world.campaign.id)]


async def test_a_mobilizer_may_not_add_anyone(client: httpx.AsyncClient, world: World) -> None:
    response = await client.post(
        "/api/users/", headers=world.headers("mobilizer"), json=_mobilizer(world)
    )
    assert response.status_code == 403
    assert response.json()["detail"] == TEAM_ONLY


async def test_nobody_removes_a_login_on_another_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await make_user(session, username="rival", role=UserRole.MANAGER)
    head = auth(await sign_in(client, "rival"))

    response = await client.delete(f"/api/users/{world.mobilizer_user.id}/", headers=head)

    assert response.status_code == 404
