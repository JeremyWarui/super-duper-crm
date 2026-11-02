"""Who reaches each finance route and the campaign's own subscription route."""

import re
import uuid

import httpx
import pytest
from fastapi.routing import APIRoute, iter_route_contexts
from sqlalchemy.ext.asyncio import AsyncSession

from backend.main import app
from backend.models import PartyRoleName, User
from tests.conftest import World
from tests.factories import auth, make_officer, sign_in

FINANCE_ROUTES = sorted(
    (method, route.path)
    for route in iter_route_contexts(app.routes)
    if isinstance(route.original_route, APIRoute) and route.path.startswith("/api/party/finance/")
    for method in route.methods - {"HEAD", "OPTIONS"}
)

# Every login the permissions table names, and whether it may use the finance routes.
FINANCE_ANSWERS = {
    "anonymous": False,
    "candidate": False,
    "manager": False,
    "mobilizer": False,
    "membership_officer": False,
    "nominations_officer": False,
    "unlinked_finance_officer": False,
    "finance_officer": True,
    "superuser": True,
}

OFFICES = {
    "membership_officer": PartyRoleName.MEMBERSHIP_OFFICER,
    "nominations_officer": PartyRoleName.NOMINATIONS_OFFICER,
    "finance_officer": PartyRoleName.FINANCE_OFFICER,
    "unlinked_finance_officer": PartyRoleName.FINANCE_OFFICER,
}


async def _headers(
    who: str, client: httpx.AsyncClient, session: AsyncSession, world: World, admin: dict
) -> dict:
    if who == "anonymous":
        return {}
    if who == "superuser":
        return admin
    if who in OFFICES:
        officer: User = await make_officer(session, world.ward, OFFICES[who], username=who[:20])
        if who.startswith("unlinked"):
            officer.party_member_id = None
            await session.commit()
        return auth(await sign_in(client, officer.username))
    return world.headers(who)


def _url(path: str) -> str:
    return re.sub(r"\{[^}]+\}", lambda _: str(uuid.uuid4()), path)


def test_the_matrix_covers_every_finance_route() -> None:
    assert len(FINANCE_ROUTES) == 14


@pytest.mark.parametrize("who", FINANCE_ANSWERS)
async def test_every_finance_route_answers_each_login_as_the_permissions_table_says(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    admin_headers: dict,
    who: str,
) -> None:
    headers = await _headers(who, client, session, world, admin_headers)
    refused = 401 if who == "anonymous" else 403

    answers = {
        (method, path): (
            await client.request(method, _url(path), headers=headers, json={})
        ).status_code
        for method, path in FINANCE_ROUTES
    }

    if FINANCE_ANSWERS[who]:
        assert not {route: code for route, code in answers.items() if code in (401, 403)}
    else:
        assert answers == {route: refused for route in FINANCE_ROUTES}


@pytest.mark.parametrize(
    "who", ["anonymous", *OFFICES, "superuser", "candidate", "manager", "mobilizer"]
)
async def test_only_a_campaign_login_reads_its_own_subscription(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    admin_headers: dict,
    who: str,
) -> None:
    headers = await _headers(who, client, session, world, admin_headers)

    answer = await client.get("/api/subscription/", headers=headers)

    wanted = {"anonymous": 401, "candidate": 200, "manager": 200, "mobilizer": 200}
    assert answer.status_code == wanted.get(who, 403)
