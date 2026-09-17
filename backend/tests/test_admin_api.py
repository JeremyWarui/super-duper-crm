"""The admin console: only a superuser reaches it, and what it reads and changes."""

import re
import uuid

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    AuthToken,
    Campaign,
    CampaignMember,
    Constituency,
    Event,
    Mobilizer,
    OfficeLevel,
    Supporter,
    Target,
    User,
    UserRole,
    Ward,
)
from tests.conftest import World
from tests.factories import (
    TEST_PASSWORD,
    auth,
    fresh_password,
    make_rival_campaign,
    make_user,
    members_of,
    sign_in,
)

SAMPLE = "00000000-0000-0000-0000-000000000001"


def _admin_gets() -> list[str]:
    """Every admin GET the app serves, read off the app so a new one is covered."""
    from backend.main import app

    return sorted(
        re.sub(r"\{[^}]+\}", SAMPLE, path)
        for path, methods in app.openapi()["paths"].items()
        if path.startswith("/api/admin/") and "get" in methods
    )


WRITES = [
    ("post", "/api/admin/users/", {"username": "someone", "role": "manager"}),
    ("post", f"/api/admin/users/{SAMPLE}/reset-password/", {}),
    ("post", f"/api/admin/users/{SAMPLE}/active/", {"active": False}),
    ("patch", "/api/admin/campaigns/{campaign}/", {"title": "Mine Now"}),
    ("delete", "/api/admin/campaigns/{campaign}/", None),
    ("post", "/api/admin/campaigns/{campaign}/members/", {"user": SAMPLE}),
    ("delete", f"/api/admin/campaigns/{{campaign}}/members/{SAMPLE}/", None),
]


def _url(world: World, path: str) -> str:
    return path.replace("{campaign}", str(world.campaign.id))


@pytest.mark.parametrize("path", _admin_gets())
async def test_the_admin_reads_need_a_token(client: httpx.AsyncClient, path: str) -> None:
    assert (await client.get(path)).status_code == 401


@pytest.mark.parametrize("path", _admin_gets())
@pytest.mark.parametrize("role", ["candidate", "manager", "mobilizer"])
async def test_no_campaign_role_reads_the_console(
    client: httpx.AsyncClient, world: World, path: str, role: str
) -> None:
    response = await client.get(path, headers=world.headers(role))

    assert response.status_code == 403
    assert response.json()["detail"] == "This is not yours to see."


@pytest.mark.parametrize(("method", "path", "body"), WRITES)
@pytest.mark.parametrize("role", ["candidate", "manager", "mobilizer"])
async def test_no_campaign_role_writes_through_the_console(
    client: httpx.AsyncClient, world: World, role: str, method: str, path: str, body: dict | None
) -> None:
    kwargs = {"headers": world.headers(role)}
    if body is not None:
        kwargs["json"] = body
    response = await client.request(method.upper(), _url(world, path), **kwargs)

    assert response.status_code == 403


async def test_the_overview_counts_everything_and_lists_each_campaign_with_its_team_and_wards(
    client: httpx.AsyncClient, world: World, admin_headers: dict
) -> None:
    body = (await client.get("/api/admin/overview/", headers=admin_headers)).json()

    assert body["totals"] == {
        "campaigns": 1,
        "users": 4,
        "members": 3,
        "targets": 2,
        "mobilizers": 1,
        "events": 0,
        "supporters": 0,
    }
    (campaign,) = body["campaigns"]
    assert campaign["title"] == "Jane for Roysambu"
    assert campaign["candidate"] == "jane"
    assert {m["username"]: m["role"] for m in campaign["members"]} == {
        "jane": "candidate",
        "amina": "manager",
        "juma": "mobilizer",
    }
    assert {w["name"] for w in campaign["wards"]} == {"Zimmerman", "Githurai"}
    assert (campaign["targets"], campaign["mobilizers"]) == (2, 1)
    assert campaign["votes_needed"] > 0

    one = await client.get(f"/api/admin/campaigns/{world.campaign.id}/", headers=admin_headers)
    assert one.json() == campaign


async def test_the_console_still_lists_a_campaign_its_manager_was_taken_off(
    client: httpx.AsyncClient, world: World, admin_headers: dict
) -> None:
    off = await client.delete(
        f"/api/admin/campaigns/{world.campaign.id}/members/{world.manager.id}/",
        headers=admin_headers,
    )

    listed = (await client.get("/api/admin/campaigns/", headers=admin_headers)).json()

    assert off.status_code == 204
    assert [c["title"] for c in listed] == ["Jane for Roysambu"]
    assert (await client.get("/api/campaigns/", headers=world.headers("manager"))).json() == []


async def test_the_user_list_names_every_login_its_campaign_and_filters(
    client: httpx.AsyncClient, world: World, admin_headers: dict
) -> None:
    body = (await client.get("/api/admin/users/", headers=admin_headers)).json()
    managers = (await client.get("/api/admin/users/?role=manager", headers=admin_headers)).json()
    on_it = (
        await client.get(f"/api/admin/users/?campaign={world.campaign.id}", headers=admin_headers)
    ).json()

    assert {u["username"]: u["campaign"] for u in body} == {
        "amina": "Jane for Roysambu",
        "jane": "Jane for Roysambu",
        "juma": "Jane for Roysambu",
        "root": None,
    }
    assert all("password" not in u and "password_hash" not in u for u in body)
    assert sorted(u["username"] for u in managers) == ["amina", "root"]
    assert sorted(u["username"] for u in on_it) == ["amina", "jane", "juma"]


async def test_a_reset_hands_back_a_working_password_and_signs_the_old_session_out(
    client: httpx.AsyncClient, world: World, admin_headers: dict
) -> None:
    before = world.headers("candidate")
    chosen = fresh_password()

    generated = await client.post(
        f"/api/admin/users/{world.candidate.id}/reset-password/", headers=admin_headers, json={}
    )
    picked = await client.post(
        f"/api/admin/users/{world.candidate.id}/reset-password/",
        headers=admin_headers,
        json={"password": chosen},
    )

    assert generated.json()["username"] == "jane"
    assert len(generated.json()["password"]) >= 12
    assert picked.json()["password"] == chosen
    assert (await client.get("/api/campaigns/", headers=before)).status_code == 401
    assert await sign_in(client, "jane", chosen)


@pytest.mark.parametrize(
    ("user", "body", "code", "message"),
    [
        ("candidate", {"password": fresh_password()[:5]}, 400, "password"),
        ("unknown", {}, 404, "No such user."),
        ("disabled", {}, 400, "disabled"),
    ],
)
async def test_a_reset_the_console_cannot_make_is_refused(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    admin_headers: dict,
    user: str,
    body: dict,
    code: int,
    message: str,
) -> None:
    user_id = {
        "candidate": world.candidate.id,
        "unknown": uuid.uuid4(),
        "disabled": world.manager.id,
    }[user]
    if user == "disabled":
        world.manager.is_active = False
        await session.commit()

    reply = await client.post(
        f"/api/admin/users/{user_id}/reset-password/", headers=admin_headers, json=body
    )

    assert reply.status_code == code
    assert message in reply.json()["detail"]


@pytest.mark.parametrize("who", ["candidate", "manager", "mobilizer"])
async def test_disabling_a_login_stops_it_at_once_until_it_is_enabled(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict, who: str
) -> None:
    target = world.mobilizer_user if who == "mobilizer" else getattr(world, who)

    off = await client.post(
        f"/api/admin/users/{target.id}/active/", headers=admin_headers, json={"active": False}
    )

    assert off.status_code == 200, off.text
    assert off.json()["is_active"] is False
    assert (await client.get("/api/campaigns/", headers=world.headers(who))).status_code == 401
    assert await session.scalar(select(AuthToken).where(AuthToken.user_id == target.id)) is None
    refused = await client.post(
        "/api/auth/login/", json={"username": target.username, "password": TEST_PASSWORD}
    )
    assert refused.status_code == 400

    await client.post(
        f"/api/admin/users/{target.id}/active/", headers=admin_headers, json={"active": True}
    )
    assert await sign_in(client, target.username)


async def test_the_console_never_deletes_a_login(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    reply = await client.delete(f"/api/admin/users/{world.manager.id}/", headers=admin_headers)

    assert reply.status_code in (404, 405)
    assert await session.get(User, world.manager.id) is not None


async def test_an_admin_cannot_disable_themselves_but_can_disable_another_admin(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    root = await session.scalar(select(User).where(User.username == "root"))
    spare = await make_user(session, username="spare_root", role=UserRole.MANAGER)
    spare.is_superuser = True
    await session.commit()

    self_off = await client.post(
        f"/api/admin/users/{root.id}/active/", headers=admin_headers, json={"active": False}
    )
    spare_off = await client.post(
        f"/api/admin/users/{spare.id}/active/", headers=admin_headers, json={"active": False}
    )

    assert self_off.status_code == 400
    assert spare_off.json()["is_active"] is False


async def test_putting_a_login_on_a_campaign_gives_it_the_campaign_in_its_own_role(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    rescue = await make_user(session, username="rescue", role=UserRole.MANAGER)
    head = auth(await sign_in(client, "rescue"))

    asked = await client.post(
        f"/api/admin/campaigns/{world.campaign.id}/members/",
        headers=admin_headers,
        json={"user": str(rescue.id), "role": "mobilizer"},
    )
    reply = await client.post(
        f"/api/admin/campaigns/{world.campaign.id}/members/",
        headers=admin_headers,
        json={"user": str(rescue.id)},
    )
    again = await client.post(
        f"/api/admin/campaigns/{world.campaign.id}/members/",
        headers=admin_headers,
        json={"user": str(rescue.id)},
    )

    assert asked.status_code == 400
    assert reply.status_code == 201
    assert again.status_code == 201
    assert (await members_of(session, world.campaign.id))["rescue"] == "manager"
    assert [m["username"] for m in again.json()["members"]].count("rescue") == 1
    listed = (await client.get("/api/campaigns/", headers=head)).json()
    assert [c["id"] for c in listed] == [str(world.campaign.id)]


@pytest.mark.parametrize(
    ("who", "message"),
    [
        ("root", "superuser"),
        ("disabled", "disabled"),
        ("candidate", "jane is already on Jane for Roysambu; a login belongs to one campaign."),
        ("manager", "amina is already on Jane for Roysambu; a login belongs to one campaign."),
        (
            "mobilizer_user",
            "juma is already on Jane for Roysambu; a login belongs to one campaign.",
        ),
        ("aspirant", "peter is a candidate, and that campaign already has its candidate."),
        ("unknown", "No such user."),
    ],
)
async def test_the_console_refuses_a_login_that_may_not_join(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    admin_headers: dict,
    who: str,
    message: str,
) -> None:
    rival = await make_rival_campaign(session, world.other_ward)
    target = rival
    if who == "root":
        user_id = await session.scalar(select(User.id).where(User.username == "root"))
    elif who == "disabled":
        user_id = (await make_user(session, username="gone", is_active=False)).id
    elif who == "aspirant":
        user_id = (await make_user(session, username="peter", role=UserRole.CANDIDATE)).id
        target = world.campaign
    elif who == "unknown":
        user_id = uuid.uuid4()
    else:
        user_id = getattr(world, who).id

    reply = await client.post(
        f"/api/admin/campaigns/{target.id}/members/",
        headers=admin_headers,
        json={"user": str(user_id)},
    )

    assert reply.status_code == 400
    assert message in reply.json()["detail"]
    on_target = await members_of(session, target.id)
    assert "peter" not in on_target and "gone" not in on_target
    assert "root" not in on_target


async def test_taking_a_mobilizer_off_frees_their_login_for_another_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    mobilizer_id = world.mobilizer_user.id
    other = await make_rival_campaign(session, world.other_ward)

    off = await client.delete(
        f"/api/admin/campaigns/{world.campaign.id}/members/{mobilizer_id}/", headers=admin_headers
    )
    on = await client.post(
        f"/api/admin/campaigns/{other.id}/members/",
        headers=admin_headers,
        json={"user": str(mobilizer_id)},
    )

    assert off.status_code == 204
    assert on.status_code == 201, on.text
    ground = await session.get(Mobilizer, world.mobilizer.id)
    await session.refresh(ground)
    assert ground.user_id is None


@pytest.mark.parametrize(
    ("who", "code", "message"),
    [
        ("candidate", 400, "delete the campaign instead"),
        ("outsider", 400, "They are not on that campaign."),
        ("missing-campaign", 404, "No such campaign."),
    ],
)
async def test_taking_off_that_cannot_happen_is_refused(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    admin_headers: dict,
    who: str,
    code: int,
    message: str,
) -> None:
    campaign_id, user_id = world.campaign.id, world.candidate.id
    if who == "outsider":
        user_id = (await make_user(session, username="stranger")).id
    if who == "missing-campaign":
        campaign_id = uuid.uuid4()

    reply = await client.delete(
        f"/api/admin/campaigns/{campaign_id}/members/{user_id}/", headers=admin_headers
    )

    assert reply.status_code == code
    assert message in reply.json()["detail"]


async def test_an_admin_deletes_a_campaign_everything_on_it_and_its_logins(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    event = await client.post(
        "/api/events/",
        headers=world.headers("manager"),
        json={
            "campaign": str(world.campaign.id),
            "ward": str(world.ward.id),
            "title": "Zimmerman town hall",
            "venue": "Social hall",
            "scheduled_date": "2027-06-12",
            "status": "planned",
            "mobilizer": str(world.mobilizer.id),
        },
    )
    supporter = await client.post(
        "/api/supporters/",
        headers=world.headers("mobilizer"),
        json={
            "campaign": str(world.campaign.id),
            "ward": str(world.ward.id),
            "full_name": "Wanjiku Njeri",
            "phone": "+254700333444",
            "consent_given": True,
        },
    )
    assert (event.status_code, supporter.status_code) == (201, 201)

    reply = await client.delete(f"/api/admin/campaigns/{world.campaign.id}/", headers=admin_headers)

    assert reply.status_code == 204
    for table in (Campaign, CampaignMember, Target, Mobilizer, Event, Supporter):
        assert await session.scalar(select(func.count()).select_from(table)) == 0, table
    assert list(await session.scalars(select(User.username))) == ["root"]
    assert await session.scalar(select(func.count()).select_from(AuthToken)) == 1
    for who in ("candidate", "manager", "mobilizer"):
        assert (await client.get("/api/campaigns/", headers=world.headers(who))).status_code == 401
    missing = await client.delete(f"/api/admin/campaigns/{uuid.uuid4()}/", headers=admin_headers)
    assert (missing.status_code, missing.json()["detail"]) == (404, "No such campaign.")


async def test_the_console_creates_a_manager_on_a_campaign_and_an_aspirant_on_none(
    client: httpx.AsyncClient, world: World, admin_headers: dict
) -> None:
    manager = await client.post(
        "/api/admin/users/",
        headers=admin_headers,
        json={"username": "newmgr", "role": "manager", "campaign": str(world.campaign.id)},
    )
    aspirant = await client.post(
        "/api/admin/users/",
        headers=admin_headers,
        json={"username": "newaspirant", "role": "candidate"},
    )

    assert (manager.status_code, aspirant.status_code) == (201, 201)
    assert manager.json()["role"] == "manager"
    for username, created, expected in (
        ("newmgr", manager, [str(world.campaign.id)]),
        ("newaspirant", aspirant, []),
    ):
        head = auth(await sign_in(client, username, created.json()["password"]))
        assert [
            c["id"] for c in (await client.get("/api/campaigns/", headers=head)).json()
        ] == expected


async def test_a_mobilizer_made_in_the_console_works_their_ward(
    client: httpx.AsyncClient, world: World, admin_headers: dict
) -> None:
    made = await client.post(
        "/api/admin/users/",
        headers=admin_headers,
        json={
            "username": "newboots",
            "role": "mobilizer",
            "campaign": str(world.campaign.id),
            "ward": str(world.ward.id),
        },
    )

    assert made.status_code == 201, made.text
    head = auth(await sign_in(client, "newboots", made.json()["password"]))
    assert [c["id"] for c in (await client.get("/api/campaigns/", headers=head)).json()] == [
        str(world.campaign.id)
    ]
    wards = (await client.get("/api/wards/", headers=head)).json()
    assert [w["name"] for w in wards] == ["Zimmerman"]


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"role": "mobilizer", "campaign": "{campaign}"}, "ward"),
        ({"role": "mobilizer"}, "campaign and a ward"),
        ({"role": "mobilizer", "campaign": "{campaign}", "ward": "{elsewhere}"}, "not a ward"),
        ({"role": "candidate", "campaign": "{campaign}"}, "is already jane's campaign"),
        ({"role": "candidate", "campaign": "{bare}"}, "Westlands MP has no candidate."),
        ({"role": "manager", "campaign": "{missing}"}, "No such campaign."),
        ({"role": "manager", "is_superuser": True}, "is_superuser"),
    ],
)
async def test_a_login_the_console_cannot_make_is_refused_and_not_created(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    admin_headers: dict,
    body: dict,
    message: str,
) -> None:
    elsewhere_constituency = Constituency(county_id=world.county.id, name="Westlands", code="280")
    elsewhere = Ward(constituency=elsewhere_constituency, name="Parklands", code="1400")
    bare = Campaign(
        title="Westlands MP",
        office_level=OfficeLevel.CONSTITUENCY,
        constituency=elsewhere_constituency,
    )
    session.add_all([elsewhere_constituency, elsewhere, bare])
    await session.commit()
    ids = {
        "{campaign}": str(world.campaign.id),
        "{elsewhere}": str(elsewhere.id),
        "{bare}": str(bare.id),
        "{missing}": str(uuid.uuid4()),
    }
    session.expunge_all()

    refused = await client.post(
        "/api/admin/users/",
        headers=admin_headers,
        json={"username": "second", **{k: ids.get(v, v) for k, v in body.items()}},
    )

    assert refused.status_code == 400
    assert message in refused.json()["detail"]
    assert await session.scalar(select(User).where(User.username == "second")) is None


async def test_a_username_taken_even_mid_request_is_refused(
    client: httpx.AsyncClient, world: World, admin_headers: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The unique constraint rules when a concurrent create wins the gap after the check."""
    from backend.services import accounts

    async def _missed(*_):
        return None

    plain = await client.post(
        "/api/admin/users/", headers=admin_headers, json={"username": "amina", "role": "manager"}
    )
    monkeypatch.setattr(accounts, "user_named", _missed)
    raced = await client.post(
        "/api/admin/users/", headers=admin_headers, json={"username": "amina", "role": "manager"}
    )

    for reply in (plain, raced):
        assert (reply.status_code, reply.json()["detail"]) == (
            400,
            "The username amina is already taken.",
        )


async def test_a_rename_changes_the_name_the_team_sees_and_nothing_else(
    client: httpx.AsyncClient, world: World, admin_headers: dict
) -> None:
    path = f"/api/admin/campaigns/{world.campaign.id}/"
    before = (await client.get(path, headers=admin_headers)).json()

    renamed = await client.patch(
        path, headers=admin_headers, json={"title": "Jane for Roysambu 2027"}
    )

    assert renamed.status_code == 200, renamed.text
    assert renamed.json() == {**before, "title": "Jane for Roysambu 2027"}
    seen = await client.get("/api/campaigns/", headers=world.headers("manager"))
    assert [c["title"] for c in seen.json()] == ["Jane for Roysambu 2027"]


async def test_a_rename_to_nothing_or_of_nothing_is_refused(
    client: httpx.AsyncClient, world: World, admin_headers: dict
) -> None:
    blank = await client.patch(
        f"/api/admin/campaigns/{world.campaign.id}/", headers=admin_headers, json={"title": "   "}
    )
    ghost = await client.patch(
        f"/api/admin/campaigns/{uuid.uuid4()}/", headers=admin_headers, json={"title": "Ghost"}
    )

    assert blank.status_code == 400
    assert ghost.status_code == 404
    kept = await client.get(f"/api/admin/campaigns/{world.campaign.id}/", headers=admin_headers)
    assert kept.json()["title"] == "Jane for Roysambu"


async def test_a_path_that_names_nothing_is_a_404(
    client: httpx.AsyncClient, world: World, admin_headers: dict
) -> None:
    missing = uuid.uuid4()

    for reply, detail in (
        (
            await client.get(f"/api/admin/campaigns/{missing}/", headers=admin_headers),
            "No such campaign.",
        ),
        (
            await client.post(
                f"/api/admin/users/{missing}/active/", headers=admin_headers, json={"active": False}
            ),
            "No such user.",
        ),
        (
            await client.post(
                f"/api/admin/campaigns/{missing}/members/",
                headers=admin_headers,
                json={"user": str(world.manager.id)},
            ),
            "No such campaign.",
        ),
    ):
        assert (reply.status_code, reply.json()["detail"]) == (404, detail)
