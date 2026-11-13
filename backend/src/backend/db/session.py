"""Async engine and session factory."""

import ssl
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager
from functools import lru_cache

import certifi
from sqlalchemy import update
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm.attributes import set_committed_value

from backend.config import get_settings
from backend.services.errors import NotFound, Refused

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


def get_session_factory() -> Callable[[], AbstractAsyncContextManager[AsyncSession]]:
    """FastAPI dependency: opens sessions for work that runs after the response is sent."""
    return get_sessionmaker()


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency giving one session per request, rolled back on error."""
    async with get_sessionmaker()() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


def upsert(session: AsyncSession, model: type):
    """An INSERT into `model` that takes `on_conflict_do_update` or `_do_nothing`, on Postgres
    or SQLite."""
    dialect = postgresql if session.get_bind().dialect.name == "postgresql" else sqlite
    return dialect.insert(model)


async def get_or_refuse[Row](
    session: AsyncSession,
    model: type[Row],
    row_id,
    noun: str,
    *,
    match: dict | None = None,
    **options,
) -> Row:
    """The row with this id; NotFound("No such <noun>.") when it is missing or any `match`
    column differs. `options` go to `session.get`."""
    row = await session.get(model, row_id, **options)
    if row is None or any(getattr(row, name) != value for name, value in (match or {}).items()):
        raise NotFound(f"No such {noun}.")
    return row


async def first_or_refuse(session: AsyncSession, statement, noun: str):
    """The statement's first row; NotFound("No such <noun>.") when there is none."""
    row = await session.scalar(statement)
    if row is None:
        raise NotFound(f"No such {noun}.")
    return row


def replace_fields(row: object, values: dict) -> list[str]:
    """Set every value on `row`; returns the sorted names of those that changed."""
    changed = sorted(name for name, value in values.items() if getattr(row, name, None) != value)
    for name, value in values.items():
        setattr(row, name, value)
    return changed


async def move_row(session: AsyncSession, row: object, refusal: str, *still, **values) -> None:
    """Write `values` to `row` only while every condition in `still` holds; Refused(refusal)
    when another request changed it first. The row takes the new values without a reload."""
    model = type(row)
    changed = await session.execute(
        update(model)
        .where(model.id == row.id, *still)
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        raise Refused(refusal)
    for name, value in values.items():
        set_committed_value(row, name, value)
