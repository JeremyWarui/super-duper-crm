"""Async engine and session factory."""

import ssl
from collections.abc import AsyncIterator
from functools import lru_cache

import certifi
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.config import get_settings

# asyncpg verifies these only against a root.crt file on disk, so they become an SSL context.
VERIFYING = ("verify-ca", "verify-full")


def engine_args(dsn: str) -> tuple[str, dict]:
    """The URL and connect args for an engine.

    `ssl=verify-full` checks the server's certificate and hostname against
    certifi's CA bundle; `verify-ca` checks the certificate only.
    """
    url = make_url(dsn)
    mode = url.query.get("ssl")
    if mode not in VERIFYING:
        return dsn, {}
    context = ssl.create_default_context(cafile=certifi.where())
    context.check_hostname = mode == "verify-full"
    url = url.difference_update_query(["ssl"])
    return url.render_as_string(hide_password=False), {"ssl": context}


@lru_cache
def get_engine() -> AsyncEngine:
    """The connection pool. Created on first use, then reused."""
    settings = get_settings()
    url, connect_args = engine_args(settings.database_url)
    return create_async_engine(
        url,
        echo=settings.echo_sql,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_engine(),
        expire_on_commit=False,
        autoflush=False,
    )


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency giving one session per request, rolled back on error."""
    async with get_sessionmaker()() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
