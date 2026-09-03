"""The session dependency FastAPI will use once routers exist.

Pointed at SQLite rather than the configured CockroachDB DSN, so the test needs
no server. What is under test is the wiring - caching, and the rollback on error
- not the driver.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.db.session import get_engine, get_session, get_sessionmaker


@pytest.fixture(autouse=True)
def sqlite_dsn(monkeypatch: pytest.MonkeyPatch):
    """Repoint the app's DSN, and leave the caches empty afterwards.

    `get_settings`, `get_engine` and `get_sessionmaker` are all `lru_cache`d, so
    a stale entry here would leak a SQLite engine into every later test.
    """
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
    """A failed request must not leave a half-finished transaction on the
    connection for the next request that borrows it from the pool."""
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
