"""Creating logins for the campaign team."""

import uuid

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.scope import add_member
from backend.config import get_settings
from backend.models import Campaign, Mobilizer, OfficeLevel, User, UserRole
from tests.conftest import World
from tests.factories import auth, fresh_password, make_user, sign_in


def _manager(campaign=None, **overrides) -> dict:
    body = {
        "username": "brian",
        "role": "manager",
        "first_name": "Amina",
        "last_name": "Kariuki",
        "phone": "+254700111222",
    }
    if campaign is not None:
        body["campaign"] = str(campaign)
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


async def test_a_manager_can_add_another_manager(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    response = await client.post(
        "/api/users/",
        headers=world.headers("manager"),
        json=_manager(world.campaign.id),
    )

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
    response = await client.post(
        "/api/users/",
        headers=world.headers("mobilizer"),
        json=_manager(world.campaign.id),
    )
    assert response.status_code == 403


async def test_a_mobilizer_may_not_read_the_team(client: httpx.AsyncClient, world: World) -> None:
    assert (await client.get("/api/users/", headers=world.headers("mobilizer"))).status_code == 403


# ------------------------------------------------------------- the password


async def test_the_password_comes_back_once_and_signs_them_in(
    client: httpx.AsyncClient, world: World
) -> None:
    created = (
        await client.post(
            "/api/users/",
            headers=world.headers("manager"),
            json=_manager(world.campaign.id),
        )
    ).json()

    token = await sign_in(client, "brian", created["password"])

    assert len(token) == 40


async def test_the_password_is_generated_not_chosen(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post(
        "/api/users/",
        headers=world.headers("manager"),
        json=_manager(world.campaign.id, password=fresh_password()),
    )
    assert response.status_code == 400


async def test_two_accounts_do_not_share_a_password(
    client: httpx.AsyncClient, world: World
) -> None:
    first = (
        await client.post(
            "/api/users/",
            headers=world.headers("manager"),
            json=_manager(world.campaign.id),
        )
    ).json()
    second = (
        await client.post(
            "/api/users/",
            headers=world.headers("manager"),
            json=_manager(world.campaign.id, username="carol"),
        )
    ).json()

    assert first["password"] != second["password"]
    assert len(first["password"]) >= 12


async def test_the_default_password_is_handed_to_everyone_onboarded(
    client: httpx.AsyncClient, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DEFAULT_USER_PASSWORD gives a demo one credential for the whole team."""
    shared = fresh_password()
    monkeypatch.setenv("DEFAULT_USER_PASSWORD", shared)
    get_settings.cache_clear()
    try:
        created = (
            await client.post(
                "/api/users/",
                headers=world.headers("manager"),
                json=_manager(world.campaign.id),
            )
        ).json()
    finally:
        get_settings.cache_clear()

    assert created["password"] == shared
    assert await sign_in(client, "brian", shared)


async def test_the_password_is_not_readable_afterwards(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    created = (
        await client.post(
            "/api/users/",
            headers=world.headers("manager"),
            json=_manager(world.campaign.id),
        )
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
        await client.post(
            "/api/users/",
            headers=world.headers("manager"),
            json=_manager(world.campaign.id),
        )
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
    await client.post(
        "/api/users/",
        headers=world.headers("manager"),
        json=_manager(world.campaign.id),
    )

    response = await client.post(
        "/api/users/",
        headers=world.headers("manager"),
        json=_manager(world.campaign.id, first_name="Someone"),
    )

    assert response.status_code == 400
    assert "already taken" in response.json()["detail"]


async def test_a_username_with_spaces_or_symbols_is_refused(
    client: httpx.AsyncClient, world: World
) -> None:
    for bad in ["a b", "amina!", "amina@example.com", "am"]:
        response = await client.post(
            "/api/users/",
            headers=world.headers("manager"),
            json=_manager(str(world.campaign.id), username=bad),
        )
        assert response.status_code == 400, bad


async def test_a_candidate_cannot_be_created_this_way(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post(
        "/api/users/",
        headers=world.headers("manager"),
        json=_manager(str(world.campaign.id), role="candidate"),
    )
    assert response.status_code == 400


async def test_a_superuser_cannot_be_asked_for(client: httpx.AsyncClient, world: World) -> None:
    response = await client.post(
        "/api/users/",
        headers=world.headers("manager"),
        json=_manager(world.campaign.id, is_superuser=True),
    )
    assert response.status_code == 400


# --------------------------------------------------------------- removing


async def test_a_login_can_be_removed(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    created = (
        await client.post(
            "/api/users/",
            headers=world.headers("manager"),
            json=_manager(world.campaign.id),
        )
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


# ------------------------------------------------------- who the team is for


async def test_a_created_manager_joins_the_campaign_rather_than_an_empty_app(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    theirs = str(world.campaign.id)
    created = (
        await client.post("/api/users/", headers=world.headers("manager"), json=_manager(theirs))
    ).json()

    token = await sign_in(client, "brian", created["password"])
    listed = (await client.get("/api/campaigns/", headers=auth(token))).json()

    assert [c["id"] for c in listed] == [theirs]


async def test_a_manager_with_no_campaign_is_refused(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post("/api/users/", headers=world.headers("manager"), json=_manager())

    assert response.status_code == 400
    assert "sign in to nothing" in response.json()["detail"]


async def test_a_manager_cannot_be_added_to_a_campaign_the_caller_cannot_see(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """A campaign that exists and belongs to somebody else, not a made-up id."""
    stranger = await make_user(session, username="stranger", role=UserRole.MANAGER)
    theirs = Campaign(
        title="Not Yours",
        office_level=OfficeLevel.WARD,
        ward_id=world.other_ward.id,
    )
    session.add(theirs)
    await session.flush()
    await add_member(session, theirs.id, stranger.id)
    await session.commit()

    response = await client.post(
        "/api/users/", headers=world.headers("manager"), json=_manager(theirs.id)
    )

    assert response.status_code == 404


async def test_a_fresh_manager_sees_only_themselves_so_setup_asks_for_a_new_aspirant(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """An empty aspirant list is what sends the sign-up flow to the new-aspirant form."""
    from tests.factories import make_user

    await make_user(session, username="newmanager", role=UserRole.MANAGER)
    token = await sign_in(client, "newmanager")

    aspirants = (await client.get("/api/users/?role=candidate", headers=auth(token))).json()
    everyone = (await client.get("/api/users/", headers=auth(token))).json()

    assert aspirants == []
    assert [u["username"] for u in everyone] == ["newmanager"]


async def test_a_manager_sees_the_team_of_the_campaign_they_run(
    client: httpx.AsyncClient, world: World
) -> None:
    listed = (await client.get("/api/users/", headers=world.headers("manager"))).json()

    assert sorted(u["username"] for u in listed) == ["amina", "jane", "juma"]


async def test_a_manager_cannot_remove_somebody_on_another_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    from tests.factories import make_user

    await make_user(session, username="rival", role=UserRole.MANAGER)
    token = await sign_in(client, "rival")

    response = await client.delete(f"/api/users/{world.mobilizer_user.id}/", headers=auth(token))

    assert response.status_code == 404


async def test_a_candidate_may_not_appoint_a_manager(
    client: httpx.AsyncClient, world: World
) -> None:
    """The manager runs the campaign, so the manager builds the team."""
    response = await client.post(
        "/api/users/", headers=world.headers("candidate"), json=_manager(world.campaign.id)
    )

    assert response.status_code == 403
    assert "Only a campaign manager may add another" in response.json()["detail"]


async def test_adding_a_colleague_does_not_evict_the_manager_doing_it(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """The whole point of a membership row rather than a column."""
    before = (await client.get("/api/campaigns/", headers=world.headers("manager"))).json()

    response = await client.post(
        "/api/users/",
        headers=world.headers("manager"),
        json=_manager(str(world.campaign.id), username="colleague"),
    )
    assert response.status_code == 201, response.text

    after = (await client.get("/api/campaigns/", headers=world.headers("manager"))).json()
    assert [c["id"] for c in after] == [c["id"] for c in before]

    token = await sign_in(client, "colleague", response.json()["password"])
    theirs = (await client.get("/api/campaigns/", headers=auth(token))).json()
    assert [c["id"] for c in theirs] == [str(world.campaign.id)]
