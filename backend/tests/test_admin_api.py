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
    OrganisationType,
    Supporter,
    Target,
    User,
)
from tests.conftest import World
from tests.factories import (
    TEST_PASSWORD,
    claim_link,
    email_of,
    fresh_password,
    sign_in,
)
from tests.test_route_guards import party_only_routes

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
    client: httpx.AsyncClient,
    world: World,
    path: str,
    role: str,
    organisation_type: OrganisationType,
) -> None:
    unmounted = organisation_type is not OrganisationType.PARTY and path in {
        re.sub(r"\{[^}]+\}", SAMPLE, route) for _, route in party_only_routes()
    }

    response = await client.get(path, headers=world.headers(role))

    if unmounted:
        assert response.status_code == 404
    else:
        assert response.status_code == 403
        assert response.json()["detail"] == "This is not yours to see."


async def test_a_reset_emails_a_link_and_using_it_signs_the_old_session_out(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    before = world.headers("candidate")
    chosen = fresh_password()

    sent = await client.post(
        f"/api/admin/users/{world.candidate.id}/reset-password/", headers=admin_headers
    )
    still_in = (await client.get("/api/campaigns/", headers=before)).status_code
    await claim_link(client, session, email_of("jane"), chosen)

    assert sent.json() == {"username": "jane", "sent": "email"}
    assert still_in == 200
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
        "/api/auth/login/", json={"email": target.email, "password": TEST_PASSWORD}
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


async def test_the_console_gives_a_campaign_no_second_manager_and_no_lone_aspirant(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    manager = await client.post(
        "/api/admin/users/",
        headers=admin_headers,
        json={"username": "newmgr", "role": "manager", "campaign": str(world.campaign.id)},
    )
    aspirant = await client.post(
        "/api/admin/users/",
        headers=admin_headers,
        json={"username": "loneaspirant", "role": "candidate"},
    )

    assert (manager.status_code, manager.json()["detail"]) == (
        400,
        "That campaign already has a manager, amina. "
        "Its aspirant replaces them from the Team page.",
    )
    assert (aspirant.status_code, aspirant.json()["detail"]) == (
        400,
        "An aspirant gets their login with their workspace, from Aspirants or at setup.",
    )
    for gone in ("newmgr", "loneaspirant"):
        assert await session.scalar(select(User).where(User.username == gone)) is None


async def test_a_mobilizer_made_in_the_console_works_the_ward_given(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    created = await client.post(
        "/api/admin/users/",
        headers=admin_headers,
        json={
            "username": "wanjiku",
            "role": "mobilizer",
            "campaign": str(world.campaign.id),
            "ward": str(world.other_ward.id),
        },
    )

    assert created.status_code == 201
    ground = await session.scalar(
        select(Mobilizer).where(Mobilizer.user_id == uuid.UUID(created.json()["id"]))
    )
    assert ground is not None and ground.ward_id == world.other_ward.id


async def test_the_console_makes_no_campaign_itself(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    response = await client.post(
        "/api/admin/campaigns/",
        headers=admin_headers,
        json={"title": "Straight from the console", "seat": "mp"},
    )

    assert response.status_code == 405
    assert await session.scalar(select(Campaign).where(Campaign.title.like("Straight%"))) is None


async def test_the_console_changes_a_login_s_email_and_the_login_signs_in_with_it(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    url = f"/api/admin/users/{world.mobilizer_user.id}/email/"
    taken = await client.put(url, headers=admin_headers, json={"email": world.manager.email})
    changed = await client.put(url, headers=admin_headers, json={"email": " Juma@Example.TEST "})

    assert (taken.status_code, taken.json()["detail"]) == (
        400,
        f"The email {world.manager.email} already belongs to another login.",
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["email"] == "juma@example.test"
    assert await sign_in(client, "juma@example.test")


async def test_the_console_pages_logins_by_username_and_lists_all_without_a_limit(
    client: httpx.AsyncClient, world: World, admin_headers: dict[str, str]
) -> None:
    every = (await client.get("/api/admin/users/", headers=admin_headers)).json()
    pages = [
        (await client.get(f"/api/admin/users/?limit=2&offset={offset}", headers=admin_headers))
        for offset in (0, 2, len(every))
    ]

    names = [u["username"] for u in every]
    assert names == sorted(names) and {"jane", "juma", "root"} <= set(names)
    assert world.campaign.title in {u["campaign"] for u in every}
    assert [p.json() for p in pages] == [every[:2], every[2:4], []]
