"""A campaign runs its own team: the aspirant sets the manager, and the team resets passwords."""

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AuthToken, CampaignMember, RegistrationCentre, User, UserRole
from tests.conftest import World
from tests.factories import TEST_PASSWORD, auth, make_campaign, make_user, sign_in


def _team(world: World, *rest: str) -> str:
    return "/".join([f"/api/campaigns/{world.campaign.id}/team", *rest, ""])


async def _logins(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(User))


async def test_only_the_aspirant_adds_the_manager_and_only_by_replacing_the_one_there(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    await make_campaign(session, world.other_ward)
    other_aspirant = auth(await sign_in(client, f"candidate-{world.other_ward.code}"))
    body = {"username": "wanjiru", "first_name": "Wanjiru"}
    before = await _logins(session)

    def add(headers: dict):
        return client.post(_team(world, "manager"), headers=headers, json=body)

    refused = {
        "manager": (await add(world.headers("manager"))).status_code,
        "mobilizer": (await add(world.headers("mobilizer"))).status_code,
        "superuser": (await add(admin_headers)).status_code,
        "another campaign's aspirant": (await add(other_aspirant)).status_code,
    }
    without_replace = await add(world.headers("candidate"))

    assert refused == {
        "manager": 403,
        "mobilizer": 403,
        "superuser": 403,
        "another campaign's aspirant": 404,
    }
    assert (without_replace.status_code, without_replace.json()["detail"]) == (
        400,
        "Jane for Roysambu already has a manager, amina. Replace them instead.",
    )
    assert await _logins(session) == before


async def test_replacing_the_manager_signs_the_old_one_out_and_off_the_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    response = await client.post(
        _team(world, "manager"),
        headers=world.headers("candidate"),
        json={"username": "wanjiru", "first_name": "Wanjiru", "replace": True},
    )

    made = response.json()
    assert (response.status_code, made["username"], made["replaced"]) == (201, "wanjiru", "amina")
    assert (
        await client.get("/api/campaigns/", headers=world.headers("manager"))
    ).status_code == 401
    head = auth(await sign_in(client, "wanjiru", made["password"]))
    assert [c["id"] for c in (await client.get("/api/campaigns/", headers=head)).json()] == [
        str(world.campaign.id)
    ]
    await session.refresh(world.manager)
    assert world.manager.is_active is False
    tokens = await session.scalar(
        select(func.count()).select_from(AuthToken).where(AuthToken.user_id == world.manager.id)
    )
    assert tokens == 0
    managers = await session.scalars(
        select(CampaignMember.user_id).where(
            CampaignMember.campaign_id == world.campaign.id,
            CampaignMember.role == UserRole.MANAGER,
        )
    )
    assert [str(m) for m in managers] == [made["id"]]


async def test_a_refused_replace_keeps_the_manager_there_and_makes_no_login(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    before = await _logins(session)
    response = await client.post(
        _team(world, "manager"),
        headers=world.headers("candidate"),
        json={"username": "juma", "replace": True},
    )

    assert (response.status_code, response.json()["detail"]) == (
        400,
        "The username juma is already taken.",
    )
    assert (
        await client.get("/api/campaigns/", headers=world.headers("manager"))
    ).status_code == 200
    assert await _logins(session) == before


async def test_the_database_holds_one_manager_per_campaign_whatever_the_route(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    admin_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    second = await make_user(session, username="second", role=UserRole.MANAGER)
    members = f"/api/admin/campaigns/{world.campaign.id}/members/"

    checked = await client.post(members, headers=admin_headers, json={"user": str(second.id)})

    async def no_check(*_args) -> None:
        return None

    # Two requests racing past the check both reach the insert; the index stops the second.
    monkeypatch.setattr("backend.services.accounts.membership_refusal", no_check)
    raced = await client.post(members, headers=admin_headers, json={"user": str(second.id)})

    assert (checked.status_code, checked.json()["detail"]) == (
        400,
        "That campaign already has a manager, amina. "
        "Its aspirant replaces them from the Team page.",
    )
    assert (raced.status_code, raced.json()["detail"]) == (
        400,
        "That campaign already has its aspirant or its manager.",
    )


async def test_the_aspirant_resets_the_manager_and_the_manager_only_mobilizers(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    outsider = await make_user(session, username="stranger", role=UserRole.MOBILIZER)
    idle = await make_user(session, username="idle", role=UserRole.MOBILIZER, is_active=False)
    session.add(CampaignMember(campaign_id=world.campaign.id, user_id=idle.id, role=idle.role))
    await session.commit()

    def reset(role: str, user: User):
        return client.post(
            _team(world, str(user.id), "reset-password"), headers=world.headers(role)
        )

    refused = {
        "aspirant by manager": (await reset("manager", world.candidate)).status_code,
        "manager by self": (await reset("manager", world.manager)).status_code,
        "by mobilizer": (await reset("mobilizer", world.mobilizer_user)).status_code,
        "off the campaign": (await reset("candidate", outsider)).status_code,
        "turned off": (await reset("manager", idle)).status_code,
    }
    mobilizer_by_manager = await reset("manager", world.mobilizer_user)
    manager_by_aspirant = await reset("candidate", world.manager)

    assert manager_by_aspirant.json()["username"] == "amina"
    assert mobilizer_by_manager.status_code == 200
    assert refused == {
        "aspirant by manager": 403,
        "manager by self": 403,
        "by mobilizer": 403,
        "off the campaign": 404,
        "turned off": 400,
    }
    assert (
        await client.get("/api/campaigns/", headers=world.headers("mobilizer"))
    ).status_code == 401
    old = await client.post(
        "/api/auth/login/", json={"username": "juma", "password": TEST_PASSWORD}
    )
    assert old.status_code == 400
    await sign_in(client, "juma", mobilizer_by_manager.json()["password"])


async def test_an_mca_mobilizer_goes_on_a_targeted_centre_and_never_a_whole_ward(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    from backend.services.targets import generate_targets

    second = RegistrationCentre(
        ward=world.ward, name="Roysambu Primary", code="003", registered_voters=1_000
    )
    session.add(second)
    mca = await make_campaign(session, world.ward)
    await generate_targets(session, mca)
    untargeted = RegistrationCentre(ward=world.ward, name="Kamae", code="002")
    session.add(untargeted)
    manager = await make_user(session, username="mcamanager", role=UserRole.MANAGER)
    session.add(CampaignMember(campaign_id=mca.id, user_id=manager.id, role=UserRole.MANAGER))
    await session.commit()
    head = auth(await sign_in(client, "mcamanager"))
    ward = str(world.ward.id)

    def login(username: str, centre: RegistrationCentre | None, headers: dict = head):
        route = "/api/admin/users/" if headers is admin_headers else "/api/users/"
        return client.post(
            route,
            headers=headers,
            json={
                "username": username,
                "role": "mobilizer",
                "campaign": str(mca.id),
                "ward": ward,
                "registration_centre": str(centre.id) if centre else None,
            },
        )

    whole_ward = await login("wholeward", None)
    off_target = await login("offtarget", untargeted)
    on_target = await login("ontarget", world.centre)
    no_login = await client.post(
        "/api/mobilizers/",
        headers=head,
        json={"campaign": str(mca.id), "ward": ward, "full_name": "Wanjiku Njeri"},
    )
    moved = await client.patch(
        f"/api/mobilizers/{on_target.json()['mobilizer']}/",
        headers=head,
        json={"ward": ward, "registration_centre": str(untargeted.id)},
    )
    overview = await client.get("/api/admin/overview/", headers=admin_headers)
    by_console = await login("byconsole", second, admin_headers)

    pick_a_centre = "In an MCA race a mobilizer works one registration centre; pick a centre."
    no_target = "That centre has no target, so work there would count toward nothing."
    assert [(r.status_code, r.json()["detail"]) for r in (whole_ward, no_login)] == [
        (400, pick_a_centre)
    ] * 2
    assert [(r.status_code, r.json()["detail"]) for r in (off_target, moved)] == [
        (400, no_target)
    ] * 2
    assert on_target.status_code == 201
    listed = next(c for c in overview.json()["campaigns"] if c["id"] == str(mca.id))
    assert [c["name"] for c in listed["centres"]] == ["Roysambu Primary", "Zimmerman Primary"]
    assert by_console.status_code == 201
