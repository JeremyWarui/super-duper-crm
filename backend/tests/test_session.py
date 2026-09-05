"""The session dependency: caching, and the rollback when a request fails."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.db.session import get_engine, get_session, get_sessionmaker


@pytest.fixture(autouse=True)
def sqlite_dsn(monkeypatch: pytest.MonkeyPatch):
    """Point the app at a test database, and clear the caches on the way in and
    out so no engine leaks into another test."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite://")
    for cached in (get_settings, get_engine, get_sessionmaker):
        cached.cache_clear()
    yield
    for cached in (get_settings, get_engine, get_sessionmaker):
        cached.cache_clear()


async def test_get_session_yields_a_usable_session() -> None:
    agen = get_session()
    session = await anext(agen)
    assert isinstance(session, AsyncSession)
    assert session.is_active
    with pytest.raises(StopAsyncIteration):
        await anext(agen)


async def test_get_session_rolls_back_and_re_raises() -> None:
    agen = get_session()
    session = await anext(agen)

    with pytest.raises(RuntimeError, match="boom"):
        await agen.athrow(RuntimeError("boom"))

    assert not session.in_transaction()


async def test_the_engine_is_created_once() -> None:
    assert get_engine() is get_engine()
    assert get_sessionmaker() is get_sessionmaker()


async def test_the_engine_uses_the_configured_dsn() -> None:
    assert get_engine().url.render_as_string() == "sqlite+aiosqlite://"


# ------------------------------------------------------------- CockroachDB


async def test_a_cockroach_dsn_builds_an_async_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    """The deploy runs on CockroachDB, whose scheme needs its own dialect.

    `postgresql+asyncpg` raises AssertionError against Cockroach: SQLAlchemy
    cannot read "CockroachDB CCL v26.2.5 ..." as a version. No connection is
    made here; this only proves the dialect resolves and is async.
    """
    monkeypatch.setenv(
        "DATABASE_URL", "cockroachdb+asyncpg://u:p@host:26257/defaultdb?ssl=require"
    )
    for cached in (get_settings, get_engine, get_sessionmaker):
        cached.cache_clear()

    engine = get_engine()

    assert engine.dialect.name == "cockroachdb"
    assert engine.dialect.driver == "asyncpg"
    assert engine.dialect.is_async
