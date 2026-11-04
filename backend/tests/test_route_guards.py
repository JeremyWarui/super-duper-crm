"""Every API route needs a login unless it is on the public list."""

from fastapi import APIRouter, FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, iter_route_contexts

from backend.api.deps import CurrentUser, get_current_user, get_signed_in_user
from backend.main import app

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
