"""The ASGI application."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend import __version__
from backend.api.errors import register_error_handlers
from backend.api.routers import api_router
from backend.config import get_settings
from backend.db.session import get_engine

# Imported so every model is registered on Base.metadata.
from backend.models import Base  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await get_engine().dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Campaign CRM API",
        version=__version__,
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)
    app.include_router(api_router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    _mount_spa(app, settings.static_dir)
    return app


def _mount_spa(app: FastAPI, static_dir: str) -> None:
    """Serve the built SPA at "/", under the API rather than beside it.

    Mounted last, so /api and /docs still win. `html=True` returns index.html
    for a path with no file, which is what a refreshed SPA route needs.
    """
    if not static_dir:
        return
    directory = Path(static_dir)
    if not directory.is_dir():
        raise RuntimeError(f"STATIC_DIR is set to {directory}, which is not a directory.")
    app.mount("/", StaticFiles(directory=directory, html=True), name="spa")


app = create_app()
