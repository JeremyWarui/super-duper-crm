"""Every API route needs a login unless it is on the public list, and party routes exist only
in a party installation."""

import re

import httpx
import pytest
from fastapi import APIRouter, FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, iter_route_contexts
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import (
    CurrentUser,
    get_current_user,
    get_organisation_type,
    get_signed_in_user,
)
from backend.api.install import PartyOnlyRoute
from backend.main import app
from backend.models import OrganisationType
from backend.services import site
from tests.conftest import app_client
from tests.factories import site_settings

PUBLIC_ROUTES = {
    ("POST", "/api/auth/login/"),
    ("GET", "/api/join/{code}/"),
    ("POST", "/api/join/{code}/"),
    ("POST", "/api/join/withdraw/{code}/"),
    ("GET", "/api/site/"),
    ("GET", "/api/party/"),
    ("GET", "/api/party/places/"),
    ("GET", "/api/party/leaders/"),
    ("GET", "/api/party/slides/"),
    ("GET", "/api/party/issues/"),
    ("GET", "/api/party/issues/{issue_id}/"),
    ("GET", "/api/party/documents/"),
    ("GET", "/api/party/values/"),
    ("GET", "/api/party/organs/"),
    ("GET", "/api/party/stats/"),
    ("GET", "/api/party/results/"),
    ("GET", "/api/party/videos/"),
    ("GET", "/api/party/posts/"),
    ("GET", "/api/party/posts/{post_id}/"),
    ("POST", "/api/party/join/"),
    ("POST", "/api/party/withdraw/{code}/"),
    ("POST", "/api/party/volunteer/withdraw/{code}/"),
    ("GET", "/api/party/branches/"),
    ("GET", "/api/party/branches/{county_id}/"),
    ("POST", "/api/party/subscribe/"),
    ("POST", "/api/party/unsubscribe/{code}/"),
    ("POST", "/api/party/contribute/"),
    ("GET", "/api/candidates/"),
    ("GET", "/api/candidates/{slug}/"),
    ("POST", "/api/candidates/{slug}/volunteer/"),
    ("POST", "/api/candidates/volunteer/withdraw/{code}/"),
    ("POST", "/api/payments/paystack/webhook/"),
    ("GET", "/health"),
}


# Routes that exist only in a party installation (docs/Product_Design.md, "Organisation type"
# and "Website"). The public content under /api/party/ is the website's in both types.
PARTY_ONLY_PATHS = (
    r"^/api/party/(?!(posts|places|subscribe|unsubscribe|contribute|slides|issues|documents"
    r"|videos)/)",
    r"^/api/admin/party/($|(leaders|branches|values|organs|results|candidates)/"
    r"|posts/\{post_id\}/aspirants/)",
    r"^/api/admin/users/\{user_id\}/party-",
    r"^/api/candidates/$",
)
SAMPLE = "00000000-0000-0000-0000-000000000001"


# Signed-in routes that skip the closed-campaign check, so a closed campaign's login can still
# see who it is and sign out; and the member account, which a member login opens.
SIGNED_IN_ONLY = {
    ("GET", "/api/auth/me/"),
    ("POST", "/api/auth/logout/"),
    ("GET", "/api/account/"),
    ("PUT", "/api/account/volunteer/"),
    ("POST", "/api/account/volunteer/stop/"),
    ("POST", "/api/account/leave/"),
}


def _depends_on(dependant: Dependant, call) -> bool:
    return any(sub.call is call or _depends_on(sub, call) for sub in dependant.dependencies)


def _needs_login(dependant: Dependant) -> bool:
    return _depends_on(dependant, get_signed_in_user)


def _api_routes(application: FastAPI) -> dict[tuple[str, str], bool]:
    """Maps each (method, path) of the API to whether it depends on `get_current_user`."""
    inventory: dict[tuple[str, str], bool] = {}
    for route in iter_route_contexts(application.routes):
        if not isinstance(route.original_route, APIRoute):
            continue
        if not route.include_in_schema and not route.path.startswith("/api"):
            continue
        for method in route.methods:
            inventory[(method, route.path)] = _needs_login(route.dependant)
    return inventory


def party_only_routes() -> set[tuple[str, str]]:
    """Each (method, path) served by a `PartyOnlyRoute`."""
    return {
        (method, route.path)
        for route in iter_route_contexts(app.routes)
        if isinstance(route.original_route, PartyOnlyRoute)
        for method in route.methods
    }


def test_every_api_route_needs_a_login_unless_it_is_public():
    inventory = _api_routes(app)

    unguarded = {key for key, guarded in inventory.items() if not guarded}
    assert unguarded - PUBLIC_ROUTES == set(), "routes with no login"
    assert PUBLIC_ROUTES - set(inventory) == set(), "stale entries in PUBLIC_ROUTES"


def test_the_route_walk_reports_a_route_with_no_login():
    probe = FastAPI()
    router = APIRouter()

    @router.get("/open")
    async def open_route(): ...

    @router.get("/closed")
    async def closed_route(user: CurrentUser): ...

    probe.include_router(router)

    inventory = _api_routes(probe)
    assert {key for key, guarded in inventory.items() if not guarded} == {("GET", "/open")}
    assert inventory[("GET", "/closed")] is True


def test_only_me_logout_and_the_member_account_skip_the_closed_campaign_check():
    skipping = set()
    for route in iter_route_contexts(app.routes):
        if not isinstance(route.original_route, APIRoute):
            continue
        dependant = route.dependant
        if _needs_login(dependant) and not _depends_on(dependant, get_current_user):
            skipping |= {(method, route.path) for method in route.methods}

    assert skipping == SIGNED_IN_ONLY


def test_exactly_the_party_office_and_party_website_routes_are_party_only():
    every = set(_api_routes(app))
    expected = {
        (method, path)
        for method, path in every
        if any(re.search(pattern, path) for pattern in PARTY_ONLY_PATHS)
    }

    assert party_only_routes() == expected
    assert len(expected) > 50


@pytest.mark.parametrize("organisation_type", [OrganisationType.ASPIRANT], indirect=True)
async def test_every_party_route_is_missing_in_an_aspirant_installation(
    client: httpx.AsyncClient,
) -> None:
    asks = []
    for method, path in sorted(party_only_routes()):
        url = re.sub(r"\{[^}]+\}", SAMPLE, path)
        other = "PATCH" if method != "PATCH" else "PUT"
        asks += [
            (method, url, b"{}"),
            (method, url, b"{x"),
            (other, url, b""),
            (method, url[:-1], b""),
        ]
    answers = {
        ask: (await client.request(ask[0], ask[1], content=ask[2])).status_code for ask in asks
    }

    assert {ask: code for ask, code in answers.items() if code != 404} == {}


@pytest.mark.parametrize(
    ("stored", "expected"), [(OrganisationType.PARTY, 200), (OrganisationType.ASPIRANT, 404)]
)
async def test_the_installation_type_is_read_from_the_site_settings(
    session: AsyncSession, stored: OrganisationType, expected: int
) -> None:
    session.add(site_settings(organisation_type=stored))
    await session.commit()
    site._organisation_type = None
    try:
        async with app_client(session) as client:
            del app.dependency_overrides[get_organisation_type]
            answer = await client.get("/api/party/leaders/")
    finally:
        site._organisation_type = None

    assert answer.status_code == expected
