"""The ASGI application."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.types import Scope

from backend import __version__
from backend.api.errors import register_error_handlers
from backend.api.install import SetupGate
from backend.api.routers import api_router, site_pages
from backend.config import get_settings
from backend.db.session import get_engine, get_sessionmaker
from backend.models import Base  # noqa: F401
from backend.services import reconcile

log = logging.getLogger(__name__)


def _show_app_logs() -> None:
    """Print the app's INFO lines, which carry practice-mode emails and their links."""
    logger = logging.getLogger("backend")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)


async def _reconcile_daily(hours: int) -> None:
    """Compare the payments ledger with the payout provider every `hours`, the first time five
    minutes after start."""
    await asyncio.sleep(300)
    while True:
        try:
            async with get_sessionmaker()() as session:
                await reconcile.run(session)
        except Exception:
            log.exception("Reconciliation failed; retrying next run.")
        await asyncio.sleep(hours * 3600)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    tasks = []
    if settings.reconcile_hours > 0:
        tasks.append(asyncio.create_task(_reconcile_daily(settings.reconcile_hours)))
    yield
    for task in tasks:
        task.cancel()
    await get_engine().dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Campaign CRM API",
        version=__version__,
        debug=settings.debug,
        lifespan=lifespan,
        # Interactive docs only in development.
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
    )
    # Inside CORS, so a browser can read the 503 that sends it to /setup.
    app.add_middleware(SetupGate)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _show_app_logs()
    register_error_handlers(app)
    app.include_router(api_router)
    app.include_router(site_pages.router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    _mount_spa(app, settings.static_dir)
    return app


def _mount_spa(app: FastAPI, static_dir: str) -> None:
    """Serve the built SPA at "/", after the API so /api still wins."""
    if not static_dir:
        return
    directory = Path(static_dir)
    if not directory.is_dir():
        raise RuntimeError(f"STATIC_DIR is set to {directory}, which is not a directory.")
    app.mount("/", _SPAFiles(directory=directory, html=True), name="spa")


class _SPAFiles(StaticFiles):
    """Static files that answer an unknown page address with index.html.

    API paths and missing files (anything with an extension) still 404.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            asked = Path(path)
            if exc.status_code != 404 or asked.parts[:1] == ("api",) or asked.suffix:
                raise
            return await super().get_response("index.html", scope)


app = create_app()
