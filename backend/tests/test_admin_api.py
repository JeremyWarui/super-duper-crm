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
    Event,
    Mobilizer,
    Supporter,
    Target,
    User,
)
from tests.conftest import World
from tests.factories import (
    TEST_PASSWORD,
    auth,
    fresh_password,
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


@pytest.mark.parametrize("path", _admin_gets())
@pytest.mark.parametrize("role", ["candidate", "manager", "mobilizer"])
async def test_no_campaign_role_reads_the_console(
    client: httpx.AsyncClient, world: World, path: str, role: str
) -> None:
    response = await client.get(path, headers=world.headers(role))

    assert response.status_code == 403
    assert response.json()["detail"] == "This is not yours to see."


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


async def test_the_console_creates_a_campaign_whose_aspirant_and_manager_see_only_it(
    client: httpx.AsyncClient, world: World, admin_headers: dict
) -> None:
    response = await client.post(
        "/api/admin/campaigns/",
        headers=admin_headers,
        json={
            "title": "Wanjiku for Roysambu",
            "seat": "mp",
            "constituency": str(world.constituency.id),
            "aspirant": {"username": "wanjiku", "first_name": "Wanjiku"},
            "manager": {"username": "otieno"},
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["setup"]["units"] == 2
    assert [(m["username"], m["role"]) for m in body["campaign"]["members"]] == [
        ("wanjiku", "candidate"),
        ("otieno", "manager"),
    ]
    for login in body["logins"]:
        head = auth(await sign_in(client, login["username"], login["password"]))
        seen = (await client.get("/api/campaigns/", headers=head)).json()
        assert [c["id"] for c in seen] == [body["campaign"]["id"]]


async def test_a_refused_campaign_leaves_no_campaign_and_no_login_behind(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    response = await client.post(
        "/api/admin/campaigns/",
        headers=admin_headers,
        json={
            "title": "Clash",
            "seat": "mp",
            "constituency": str(world.constituency.id),
            "aspirant": {"username": "wanjiku"},
            "manager": {"username": "amina"},
        },
    )

    assert (response.status_code, response.json()["detail"]) == (
        400,
        "The username amina is already taken.",
    )
    assert await session.scalar(select(Campaign).where(Campaign.title == "Clash")) is None
    assert await session.scalar(select(User).where(User.username == "wanjiku")) is None


@pytest.mark.parametrize("role", ["candidate", "manager", "mobilizer"])
async def test_only_a_superuser_creates_a_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World, role: str
) -> None:
    response = await client.post(
        "/api/admin/campaigns/",
        headers=world.headers(role),
        json={
            "title": "Not yours",
            "seat": "mp",
            "constituency": str(world.constituency.id),
            "aspirant": {"username": "wanjiku"},
        },
    )

    assert response.status_code == 403
    assert await session.scalar(select(Campaign).where(Campaign.title == "Not yours")) is None
