"""Fixtures: an in-memory database built from the real schema."""

import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")

from backend.models import Base  # noqa: E402  - after the env var is set


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine("sqlite+aiosqlite://")

    # SQLite ignores foreign keys unless this is on.
    @event.listens_for(engine.sync_engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
async def fk_check(session: AsyncSession) -> None:
    """Confirm foreign keys are enforced on this connection."""
    result = await session.execute(text("PRAGMA foreign_keys"))
    assert result.scalar() == 1
