"""Mobilizer logins, added and removed from inside a campaign."""

import uuid

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Mobilizer, User, UserRole
from backend.services.accounts import add_member
from tests.conftest import World
from tests.factories import auth, fresh_password, make_rival_campaign, make_user, sign_in

UNKNOWN = "00000000-0000-0000-0000-000000000009"


def _mobilizer(world: World, **overrides) -> dict:
    body = {
        "username": "wanjiku",
        "role": "mobilizer",
        "first_name": "Wanjiku",
        "last_name": "Njeri",
        "campaign": str(world.campaign.id),
        "ward": str(world.ward.id),
    }
    return {**body, **overrides}


TEAM_ONLY = "Only a candidate or a campaign manager may add or remove people."


async def test_adding_someone_needs_a_token(client: httpx.AsyncClient, world: World) -> None:
    assert (await client.post("/api/users/", json=_mobilizer(world))).status_code == 401


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
    assert created["ward_name"] == "Zimmerman"
    assert len(created["password"]) >= 12
    profile = await session.get(Mobilizer, uuid.UUID(created["mobilizer"]))
    assert (profile.ward_id, profile.full_name) == (world.ward.id, "Wanjiku Njeri")
    stored = await session.scalar(select(User).where(User.username == "wanjiku"))
    assert created["password"] not in stored.password_hash

    head = auth(await sign_in(client, "wanjiku", created["password"]))
    listed = (await client.get("/api/campaigns/", headers=head)).json()
    assert [c["id"] for c in listed] == [str(world.campaign.id)]
    wards = (await client.get("/api/wards/", headers=head)).json()
    assert [w["name"] for w in wards] == ["Zimmerman"]
    still = (await client.get("/api/campaigns/", headers=world.headers(caller))).json()
    assert [c["id"] for c in still] == [str(world.campaign.id)]


@pytest.mark.parametrize("caller", ["manager", "candidate"])
async def test_nobody_on_a_campaign_can_add_a_manager(
    client: httpx.AsyncClient, session: AsyncSession, world: World, caller: str
) -> None:
    response = await client.post(
        "/api/users/", headers=world.headers(caller), json=_mobilizer(world, role="manager")
    )

    assert response.status_code == 400
    assert response.json()["detail"].startswith("role: Only a mobilizer is added")
    assert await session.scalar(select(User).where(User.username == "wanjiku")) is None


async def test_a_mobilizer_may_not_add_anyone(client: httpx.AsyncClient, world: World) -> None:
    response = await client.post(
        "/api/users/", headers=world.headers("mobilizer"), json=_mobilizer(world)
    )
    assert response.status_code == 403
    assert response.json()["detail"] == TEAM_ONLY


async def test_two_accounts_do_not_share_a_generated_password(
    client: httpx.AsyncClient, world: World
) -> None:
    head = world.headers("manager")
    first = (await client.post("/api/users/", headers=head, json=_mobilizer(world))).json()
    second = (
        await client.post(
            "/api/users/",
            headers=head,
            json=_mobilizer(world, username="carol", ward=str(world.other_ward.id)),
        )
    ).json()

    assert first["password"] != second["password"]


async def test_the_default_password_is_handed_to_everyone_onboarded(
    client: httpx.AsyncClient,
    world: World,
    monkeypatch: pytest.MonkeyPatch,
    fresh_settings: None,
) -> None:
    shared = fresh_password()
    monkeypatch.setenv("DEFAULT_USER_PASSWORD", shared)

    created = (
        await client.post("/api/users/", headers=world.headers("manager"), json=_mobilizer(world))
    ).json()

    assert created["password"] == shared
    assert await sign_in(client, "wanjiku", shared)


@pytest.mark.parametrize(
    ("overrides", "code", "message"),
    [
        ({"password": fresh_password()}, 400, "password"),
        ({"ward": None}, 400, "ward"),
        ({"campaign": None}, 400, "campaign"),
        ({"campaign": UNKNOWN}, 404, "No such campaign."),
        ({"ward": UNKNOWN}, 400, "No such ward."),
        ({"role": "candidate"}, 400, "an aspirant is named when the campaign is set up"),
        ({"is_superuser": True}, 400, "is_superuser"),
    ],
)
async def test_a_mobilizer_the_server_cannot_make_is_refused(
    client: httpx.AsyncClient, world: World, overrides: dict, code: int, message: str
) -> None:
    response = await client.post(
        "/api/users/", headers=world.headers("manager"), json=_mobilizer(world, **overrides)
    )

    assert response.status_code == code
    assert message in response.json()["detail"]


async def test_a_mobilizer_cannot_be_added_to_a_campaign_the_caller_cannot_see(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    theirs = await make_rival_campaign(session, world.other_ward)

    response = await client.post(
        "/api/users/",
        headers=world.headers("manager"),
        json=_mobilizer(world, campaign=str(theirs.id), ward=str(world.other_ward.id)),
    )

    assert response.status_code == 404


async def test_a_username_already_taken_says_so(client: httpx.AsyncClient, world: World) -> None:
    head = world.headers("manager")
    await client.post("/api/users/", headers=head, json=_mobilizer(world))

    response = await client.post("/api/users/", headers=head, json=_mobilizer(world))

    assert response.status_code == 400
    assert response.json()["detail"] == "The username wanjiku is already taken."


@pytest.mark.parametrize("bad", ["a b", "amina!", "amina@example.com", "am"])
async def test_a_username_with_spaces_or_symbols_is_refused(
    client: httpx.AsyncClient, world: World, bad: str
) -> None:
    response = await client.post(
        "/api/users/", headers=world.headers("manager"), json=_mobilizer(world, username=bad)
    )
    assert response.status_code == 400


@pytest.mark.parametrize("caller", ["manager", "candidate"])
async def test_a_mobilizer_s_login_is_removed_and_their_ground_row_stays(
    client: httpx.AsyncClient, session: AsyncSession, world: World, caller: str
) -> None:
    created = (
        await client.post("/api/users/", headers=world.headers("manager"), json=_mobilizer(world))
    ).json()

    response = await client.delete(f"/api/users/{created['id']}/", headers=world.headers(caller))

    assert response.status_code == 204
    assert await session.scalar(select(User).where(User.username == "wanjiku")) is None
    profile = await session.get(Mobilizer, uuid.UUID(created["mobilizer"]))
    await session.refresh(profile)
    assert profile.user_id is None


async def test_you_cannot_remove_your_own_login(client: httpx.AsyncClient, world: World) -> None:
    response = await client.delete(
        f"/api/users/{world.manager.id}/", headers=world.headers("manager")
    )
    assert response.status_code == 400


@pytest.mark.parametrize(
    ("caller", "target"),
    [("manager", "candidate"), ("candidate", "manager"), ("manager", "colleague")],
)
async def test_nobody_but_a_mobilizer_is_removed_from_inside_a_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World, caller: str, target: str
) -> None:
    if target == "colleague":
        person = await make_user(session, username="colleague", role=UserRole.MANAGER)
        await add_member(session, world.campaign.id, person)
        await session.commit()
    else:
        person = getattr(world, target)

    response = await client.delete(f"/api/users/{person.id}/", headers=world.headers(caller))

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Only a mobilizer is removed from inside a campaign. An admin can disable any other login."
    )
    assert await session.get(User, person.id) is not None


async def test_a_mobilizer_may_not_remove_anyone(client: httpx.AsyncClient, world: World) -> None:
    response = await client.delete(
        f"/api/users/{world.candidate.id}/", headers=world.headers("mobilizer")
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
