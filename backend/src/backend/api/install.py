"""Routes that exist in only one type of installation.

`InstallationType` puts the organisation type on every API request shaped like such a route; a
`PartyOnlyRoute` or `AspirantOnlyRoute` matches nothing in the other type of installation, so
routing answers 404 for any method or body, exactly as for a route that was never mounted.
"""

import re
from typing import ClassVar

from fastapi import FastAPI
from fastapi.routing import APIRoute, iter_route_contexts
from starlette.routing import Match, compile_path
from starlette.types import ASGIApp, Receive, Scope, Send

from backend.api.deps import get_organisation_type
from backend.db.session import get_session
from backend.models import OrganisationType

KEY = "organisation_type"


class InstallationRoute(APIRoute):
    """A route that exists only where the installation is of `installation` type."""

    installation: ClassVar[OrganisationType]

    def matches(self, scope: Scope) -> tuple[Match, Scope]:
        if scope.get("state", {}).get(KEY) is not self.installation:
            return Match.NONE, {}
        return super().matches(scope)


class PartyOnlyRoute(InstallationRoute):
    installation = OrganisationType.PARTY


class AspirantOnlyRoute(InstallationRoute):
    installation = OrganisationType.ASPIRANT


async def installation_type(app: FastAPI) -> OrganisationType | None:
    """The organisation type, through the app's dependency overrides like any request."""
    overrides = app.dependency_overrides
    if get_organisation_type in overrides:
        return overrides[get_organisation_type]()
    sessions = overrides.get(get_session, get_session)()
    try:
        return await get_organisation_type(await anext(sessions))
    finally:
        await sessions.aclose()


def _typed_paths(app: FastAPI) -> list[re.Pattern]:
    return [
        compile_path(route.path)[0]
        for route in iter_route_contexts(app.routes)
        if isinstance(route.original_route, InstallationRoute)
    ]


class InstallationType:
    """ASGI middleware recording the organisation type on the state of each request whose
    path, with or without its trailing slash, is an installation route's."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.paths: list[re.Pattern] | None = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"].startswith("/api/"):
            if self.paths is None:
                self.paths = _typed_paths(scope["app"])
            path = scope["path"]
            toggled = path[:-1] if path.endswith("/") else f"{path}/"
            if any(p.match(path) or p.match(toggled) for p in self.paths):
                scope.setdefault("state", {})[KEY] = await installation_type(scope["app"])
        await self.app(scope, receive, send)
