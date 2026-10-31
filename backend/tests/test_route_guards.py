"""Every API route needs a login unless it is on the public list."""

from fastapi import APIRouter, FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, iter_route_contexts

from backend.api.deps import CurrentUser, get_current_user
from backend.main import app

PUBLIC_ROUTES = {
    ("POST", "/api/auth/login/"),
    ("GET", "/api/join/{code}/"),
    ("POST", "/api/join/{code}/"),
    ("POST", "/api/join/withdraw/{code}/"),
    ("GET", "/api/party/"),
    ("POST", "/api/party/join/"),
    ("POST", "/api/party/withdraw/{code}/"),
    ("GET", "/health"),
}


def _needs_login(dependant: Dependant) -> bool:
    return any(sub.call is get_current_user or _needs_login(sub) for sub in dependant.dependencies)


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
