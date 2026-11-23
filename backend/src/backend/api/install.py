"""The gate that keeps every API route but setup's closed until the installation is set up."""

from fastapi import FastAPI
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from backend.api.deps import get_set_up
from backend.db.session import get_session


async def installation_set_up(app: FastAPI) -> bool:
    """Whether setup has run, through the app's dependency overrides like any request."""
    overrides = app.dependency_overrides
    if get_set_up in overrides:
        return overrides[get_set_up]()
    sessions = overrides.get(get_session, get_session)()
    try:
        return await get_set_up(await anext(sessions))
    finally:
        await sessions.aclose()


NOT_SET_UP = "This installation is not set up yet. Open /setup with a setup token."


class SetupGate:
    """ASGI middleware answering 503 `not_set_up` to every API request but setup's until the
    installation is set up."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if (
            scope["type"] == "http"
            and path.startswith("/api/")
            and path.rstrip("/") != "/api/setup"
            and not path.startswith("/api/setup/")
            and not await installation_set_up(scope["app"])
        ):
            response = JSONResponse({"detail": NOT_SET_UP, "code": "not_set_up"}, status_code=503)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
