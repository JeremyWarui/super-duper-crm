"""ASGI application. Replaces `config/asgi.py`, `config/wsgi.py` and `config/urls.py`.

No routers are mounted: nothing but models exists yet. `/health` is the one
endpoint, so `uvicorn backend.main:app` can be verified to actually serve.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import __version__
from backend.config import get_settings
from backend.db.session import get_engine

# Imported for the side effect of populating Base.metadata.
from backend.models import Base  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    # Return pooled connections on shutdown; without this, uvicorn's reloader
    # leaks a pool per reload.
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

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
