"""Every API route needs a login unless it is on the public list."""

from fastapi import APIRouter, FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, iter_route_contexts

from backend.api.deps import CurrentUser, get_current_user, get_signed_in_user
from backend.main import app

PUBLIC_ROUTES = {
    # The homepage's candidate page and its volunteer form.
    ("GET", "/api/site/candidate/"),
    ("POST", "/api/site/volunteer/"),
    ("GET", "/api/pay/options/"),
    ("POST", "/api/pay/contribution/"),
    ("GET", "/api/pay/{reference}/"),
    # A public file; a private one answers 404 unless a superuser asks.
    ("GET", "/api/files/{file_id}/"),
    ("POST", "/api/auth/login/"),
    ("POST", "/api/auth/password-reset/"),
    # First-run setup: a setup token, not a login, opens these.
    ("GET", "/api/setup/"),
    ("POST", "/api/setup/"),
    ("POST", "/api/setup/check/"),
    ("GET", "/api/setup/areas/"),
    ("GET", "/api/team-signup/{code}/"),
    ("GET", "/api/team-signup/{code}/centres/"),
    ("POST", "/api/team-signup/{code}/"),
    ("GET", "/api/auth/links/{token}/"),
    ("POST", "/api/auth/links/{token}/"),
    ("GET", "/api/join/{code}/"),
    ("POST", "/api/join/{code}/"),
    ("POST", "/api/join/withdraw/{code}/"),
    ("GET", "/api/site/"),
    ("GET", "/api/website/places/"),
    ("GET", "/api/website/slides/"),
    ("GET", "/api/website/issues/"),
    ("GET", "/api/website/issues/{issue_id}/"),
    ("GET", "/api/website/documents/"),
    ("GET", "/api/website/videos/"),
    ("GET", "/api/website/posts/"),
    ("GET", "/api/website/posts/{post_id}/"),
    ("GET", "/api/website/events/"),
    ("GET", "/api/website/events/{event_id}/"),
    ("POST", "/api/website/subscribe/"),
    ("POST", "/api/website/unsubscribe/{code}/"),
    ("POST", "/api/website/volunteer/withdraw/{code}/"),
    ("POST", "/api/payments/paystack/webhook/"),
    # Africa's Talking's callbacks; the secret in the path is the check.
    ("POST", "/api/sms/{secret}/delivery/"),
    ("POST", "/api/sms/{secret}/inbound/"),
    ("POST", "/api/sms/{secret}/opt-out/"),
    ("POST", "/api/sms/{secret}/sozuri/delivery/"),
    ("POST", "/api/sms/{secret}/sozuri/inbound/"),
    ("GET", "/api/internal/sms/drain/"),
    ("POST", "/api/internal/sms/drain/"),
    ("POST", "/api/livekit/webhook/"),
    ("GET", "/api/push/key/"),
    ("POST", "/api/setup/target-preview/"),
    ("GET", "/health"),
}


# Signed-in routes that skip the closed-campaign check, so a closed campaign's login can still
# see who it is and sign out.
SIGNED_IN_ONLY = {
    ("GET", "/api/auth/me/"),
    ("POST", "/api/auth/logout/"),
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


def test_only_me_and_logout_skip_the_closed_campaign_check():
    skipping = set()
    for route in iter_route_contexts(app.routes):
        if not isinstance(route.original_route, APIRoute):
            continue
        dependant = route.dependant
        if _needs_login(dependant) and not _depends_on(dependant, get_current_user):
            skipping |= {(method, route.path) for method in route.methods}

    assert skipping == SIGNED_IN_ONLY
