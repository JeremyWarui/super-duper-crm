"""The engine and session: caching, rollback, the database URL as asyncpg reads it, and TLS."""

import ssl

import pytest
from sqlalchemy.engine import make_url

from backend.config import asyncpg_dsn, get_settings
from backend.db.session import engine_args, get_engine, get_session, get_sessionmaker
from tests.factories import fresh_password


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


async def test_get_session_rolls_back_and_re_raises() -> None:
    agen = get_session()
    session = await anext(agen)

    with pytest.raises(RuntimeError, match="boom"):
        await agen.athrow(RuntimeError("boom"))

    assert not session.in_transaction()


SECRET = fresh_password()

NEON = "postgresql://owner:{secret}@ep-x.ap-southeast-1.aws.neon.tech/campaign_db"


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        (
            NEON + "?sslmode=require&channel_binding=require",
            "postgresql+asyncpg://owner:{secret}@ep-x.ap-southeast-1.aws.neon.tech/campaign_db"
            "?ssl=require",
        ),
        (
            "postgres://owner:{secret}@host/db?sslmode=verify-full",
            "postgresql+asyncpg://owner:{secret}@host/db?ssl=verify-full",
        ),
        (
            "postgresql+asyncpg://owner:{secret}@host/db?sslmode=require&ssl=verify-full",
            "postgresql+asyncpg://owner:{secret}@host/db?ssl=verify-full",
        ),
        (
            "postgresql://owner:{secret}@host:5432/db",
            "postgresql+asyncpg://owner:{secret}@host:5432/db",
        ),
        ("sqlite+aiosqlite://", "sqlite+aiosqlite://"),
        ("postgresql+psycopg://owner:{secret}@host/db?sslmode=require", None),
    ],
)
def test_a_pasted_postgres_url_is_rewritten_for_asyncpg(given: str, expected: str | None) -> None:
    secret = fresh_password()
    given = given.format(secret=secret)

    assert asyncpg_dsn(given) == (expected.format(secret=secret) if expected else given)


@pytest.mark.parametrize(("mode", "checks_hostname"), [("verify-full", True), ("verify-ca", False)])
def test_a_verifying_ssl_mode_becomes_a_certificate_checking_context(
    mode: str, checks_hostname: bool
) -> None:
    url, connect_args = engine_args(f"postgresql+asyncpg://owner:{SECRET}@host/db?ssl={mode}")
    context = connect_args["ssl"]

    assert "ssl" not in make_url(url).query
    assert context.verify_mode is ssl.CERT_REQUIRED
    assert context.check_hostname is checks_hostname
