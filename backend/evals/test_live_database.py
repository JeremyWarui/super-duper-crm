"""The deployed database is reachable over TLS, migrated to head, and seeded.

Runs only with LIVE_DATABASE=1. It reads LIVE_DATABASE_URL, or DATABASE_URL
from `backend/.env`, and connects the way the app does:

    LIVE_DATABASE=1 uv run pytest evals/test_live_database.py -s
"""

import os
import time
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from dotenv import dotenv_values
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from backend.config import asyncpg_dsn
from backend.db.session import engine_args

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    os.environ.get("LIVE_DATABASE") != "1", reason="set LIVE_DATABASE=1 to check the real database"
)

# What `campaign-crm seed` loads from backend/data.
SEEDED = {"counties": 47, "constituencies": 290, "wards": 1450, "registration_centres": 27_273}


def _live_url() -> str:
    url = os.environ.get("LIVE_DATABASE_URL") or dotenv_values(ROOT / ".env").get("DATABASE_URL")
    if not url:
        pytest.fail("No LIVE_DATABASE_URL, and no DATABASE_URL in backend/.env.")
    return asyncpg_dsn(url)


@pytest.fixture
async def live() -> AsyncIterator[AsyncConnection]:
    url, connect_args = engine_args(_live_url())
    engine = create_async_engine(url, connect_args=connect_args)
    async with engine.connect() as connection:
        yield connection
    await engine.dispose()


def test_the_connection_is_encrypted() -> None:
    assert make_url(_live_url()).query.get("ssl") in ("require", "verify-ca", "verify-full")


async def test_the_schema_is_at_the_latest_migration(live: AsyncConnection) -> None:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    head = ScriptDirectory.from_config(config).get_current_head()

    applied = (await live.execute(text("select version_num from alembic_version"))).scalar()

    assert applied == head


@pytest.mark.parametrize(("table", "rows"), SEEDED.items())
async def test_the_reference_data_is_loaded(live: AsyncConnection, table: str, rows: int) -> None:
    assert (await live.execute(text(f"select count(*) from {table}"))).scalar() == rows


async def test_a_round_trip_once_awake(live: AsyncConnection) -> None:
    await live.execute(text("select 1"))
    started = time.perf_counter()
    await live.execute(text("select 1"))
    elapsed_ms = (time.perf_counter() - started) * 1000

    print(f"\nround trip: {elapsed_ms:.0f} ms")
    assert elapsed_ms < 2000
