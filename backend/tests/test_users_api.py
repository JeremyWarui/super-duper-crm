"""Creating logins for the campaign team."""

import uuid

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models import Mobilizer, User, UserRole
from tests.conftest import World
from tests.factories import auth, sign_in


def _manager(**overrides) -> dict:
    body = {
        "username": "brian",
        "role": "manager",
        "first_name": "Amina",
        "last_name": "Kariuki",
        "phone": "+254700111222",
    }
    body.update(overrides)
    return body


def _mobilizer(world: World, **overrides) -> dict:
    body = {
        "username": "wanjiku",
        "role": "mobilizer",
        "first_name": "Wanjiku",
        "last_name": "Njeri",
        "campaign": str(world.campaign.id),
        "ward": str(world.ward.id),
    }
    body.update(overrides)
    return body


# --------------------------------------------------------------- who may add


async def test_adding_someone_needs_a_token(client: httpx.AsyncClient) -> None:
    assert (await client.post("/api/users/", json=_manager())).status_code == 401


async def test_a_candidate_can_add_their_campaign_manager(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    response = await client.post("/api/users/", headers=world.headers("candidate"), json=_manager())

    assert response.status_code == 201
    assert response.json()["role"] == "manager"
    assert await session.scalar(select(User).where(User.username == "brian"))


async def test_a_manager_can_add_a_mobilizer(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    response = await client.post(
        "/api/users/", headers=world.headers("manager"), json=_mobilizer(world)
    )

    assert response.status_code == 201
    assert response.json()["ward_name"] == "Zimmerman"


async def test_a_mobilizer_may_not_add_anyone(client: httpx.AsyncClient, world: World) -> None:
    response = await client.post("/api/users/", headers=world.headers("mobilizer"), json=_manager())
    assert response.status_code == 403


async def test_a_mobilizer_may_not_read_the_team(client: httpx.AsyncClient, world: World) -> None:
    assert (await client.get("/api/users/", headers=world.headers("mobilizer"))).status_code == 403


# ------------------------------------------------------------- the password


async def test_the_password_comes_back_once_and_signs_them_in(
    client: httpx.AsyncClient, world: World
) -> None:
    created = (
        await client.post("/api/users/", headers=world.headers("candidate"), json=_manager())
    ).json()

    token = await sign_in(client, "brian", created["password"])

    assert len(token) == 40


async def test_the_password_is_generated_not_chosen(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post(
        "/api/users/",
        headers=world.headers("candidate"),
        json=_manager(password="hunter2"),
    )
    assert response.status_code == 400


async def test_two_accounts_do_not_share_a_password(
    client: httpx.AsyncClient, world: World
) -> None:
    first = (
        await client.post("/api/users/", headers=world.headers("candidate"), json=_manager())
    ).json()
    second = (
        await client.post(
            "/api/users/", headers=world.headers("candidate"), json=_manager(username="carol")
        )
    ).json()

    assert first["password"] != second["password"]
    assert len(first["password"]) >= 12


async def test_the_default_password_is_handed_to_everyone_onboarded(
    client: httpx.AsyncClient, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DEFAULT_USER_PASSWORD gives a demo one credential for the whole team."""
    monkeypatch.setenv("DEFAULT_USER_PASSWORD", "campaign1234")
    get_settings.cache_clear()
    try:
        created = (
            await client.post("/api/users/", headers=world.headers("candidate"), json=_manager())
        ).json()
    finally:
        get_settings.cache_clear()

    assert created["password"] == "campaign1234"
    assert await sign_in(client, "brian", "campaign1234")


async def test_the_password_is_not_readable_afterwards(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    created = (
        await client.post("/api/users/", headers=world.headers("candidate"), json=_manager())
    ).json()

    listed = (await client.get("/api/users/", headers=world.headers("candidate"))).json()

    assert all("password" not in row for row in listed)
    stored = (await session.execute(select(User).where(User.username == "brian"))).scalar_one()
    assert created["password"] not in stored.password_hash


# ------------------------------------------------------------- what is made


async def test_a_mobilizer_gets_the_row_that_lets_them_see_anything(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    created = (
        await client.post("/api/users/", headers=world.headers("manager"), json=_mobilizer(world))
    ).json()

    profile = (
        await session.execute(
            select(Mobilizer).where(Mobilizer.id == uuid.UUID(created["mobilizer"]))
        )
    ).scalar_one()
    assert profile.ward_id == world.ward.id
    assert profile.full_name == "Wanjiku Njeri"

    token = await sign_in(client, "wanjiku", created["password"])
    assert [w["name"] for w in (await client.get("/api/wards/", headers=auth(token))).json()] == [
        "Zimmerman"
    ]


async def test_a_mobilizer_without_a_ward_is_refused(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post(
        "/api/users/",
        headers=world.headers("manager"),
        json=_mobilizer(world, ward=None, campaign=None),
    )

    assert response.status_code == 400
    assert "sign in to nothing" in response.json()["detail"]


async def test_a_manager_gets_no_ground_team_row(client: httpx.AsyncClient, world: World) -> None:
    created = (
        await client.post("/api/users/", headers=world.headers("candidate"), json=_manager())
    ).json()
    assert created["mobilizer"] is None
    assert created["ward_name"] is None


async def test_a_mobilizer_cannot_be_put_on_a_campaign_the_caller_cannot_see(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post(
        "/api/users/",
        headers=world.headers("candidate"),
        json=_mobilizer(world, campaign="00000000-0000-0000-0000-000000000009"),
    )
    assert response.status_code == 404


async def test_an_unknown_ward_is_refused(client: httpx.AsyncClient, world: World) -> None:
    response = await client.post(
        "/api/users/",
        headers=world.headers("manager"),
        json=_mobilizer(world, ward="00000000-0000-0000-0000-000000000009"),
    )
    assert response.status_code == 400


# ------------------------------------------------------------- the username


async def test_a_username_already_taken_says_so(client: httpx.AsyncClient, world: World) -> None:
    await client.post("/api/users/", headers=world.headers("candidate"), json=_manager())

    response = await client.post(
        "/api/users/", headers=world.headers("candidate"), json=_manager(first_name="Someone")
    )

    assert response.status_code == 400
    assert "already taken" in response.json()["detail"]


async def test_a_username_with_spaces_or_symbols_is_refused(
    client: httpx.AsyncClient, world: World
) -> None:
    for bad in ["a b", "amina!", "amina@example.com", "am"]:
        response = await client.post(
            "/api/users/", headers=world.headers("candidate"), json=_manager(username=bad)
        )
        assert response.status_code == 400, bad


async def test_a_candidate_cannot_be_created_this_way(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post(
        "/api/users/", headers=world.headers("candidate"), json=_manager(role="candidate")
    )
    assert response.status_code == 400


async def test_a_superuser_cannot_be_asked_for(client: httpx.AsyncClient, world: World) -> None:
    response = await client.post(
        "/api/users/", headers=world.headers("candidate"), json=_manager(is_superuser=True)
    )
    assert response.status_code == 400


# --------------------------------------------------------------- removing


async def test_a_login_can_be_removed(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    created = (
        await client.post("/api/users/", headers=world.headers("candidate"), json=_manager())
    ).json()

    response = await client.delete(
        f"/api/users/{created['id']}/", headers=world.headers("candidate")
    )

    assert response.status_code == 204
    assert not await session.scalar(select(User).where(User.username == "brian"))


async def test_removing_a_mobilizer_s_login_keeps_the_mobilizer(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    created = (
        await client.post("/api/users/", headers=world.headers("manager"), json=_mobilizer(world))
    ).json()

    await client.delete(f"/api/users/{created['id']}/", headers=world.headers("manager"))

    profile = (
        await session.execute(
            select(Mobilizer).where(Mobilizer.id == uuid.UUID(created["mobilizer"]))
        )
    ).scalar_one()
    assert profile.user_id is None


async def test_you_cannot_remove_your_own_login(client: httpx.AsyncClient, world: World) -> None:
    response = await client.delete(
        f"/api/users/{world.manager.id}/", headers=world.headers("manager")
    )
    assert response.status_code == 400


async def test_a_candidate_holding_a_campaign_is_not_removable(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.delete(
        f"/api/users/{world.candidate.id}/", headers=world.headers("manager")
    )

    assert response.status_code == 400
    assert "delete the campaign first" in response.json()["detail"]


async def test_a_mobilizer_may_not_remove_anyone(client: httpx.AsyncClient, world: World) -> None:
    response = await client.delete(
        f"/api/users/{world.manager.id}/", headers=world.headers("mobilizer")
    )
    assert response.status_code == 403


async def test_the_team_list_names_everyone_without_their_hashes(
    client: httpx.AsyncClient, world: World
) -> None:
    body = (await client.get("/api/users/", headers=world.headers("manager"))).json()

    assert {row["username"] for row in body} == {"jane", "amina", "juma"}
    assert all("password_hash" not in row for row in body)
    assert {row["role"] for row in body} == {
        UserRole.CANDIDATE.value,
        UserRole.MANAGER.value,
        UserRole.MOBILIZER.value,
    }
