"""Fixtures: an in-memory database built from the real schema."""

import os
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

import httpx
import pytest
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")

from backend.models import Base  # noqa: E402  - after the env var is set

if TYPE_CHECKING:
    from backend.models import (
        Campaign,
        Constituency,
        County,
        Mobilizer,
        RegistrationCentre,
        User,
        Ward,
    )


@pytest.fixture(autouse=True, scope="session")
def cheap_password_hashing() -> Iterator[None]:
    """Hash at a fraction of the real cost, so the suite is not mostly Argon2.

    Argon2's real parameters spend ~64MB and ~100ms per hash on purpose. Almost
    every API test signs somebody in, so paying that here buys nothing: the
    parameters themselves are checked directly in `test_security.py`, against
    the hasher this replaces. Kept above the weak-hash fixture there, so
    `needs_rehash` still has something to reject.
    """
    from argon2 import PasswordHasher

    import backend.security as security

    real = security._hasher
    security._hasher = PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1)
    yield
    security._hasher = real


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


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    """The real app, with every request served by the in-memory session."""
    from backend.db.session import get_session
    from backend.main import app

    async def _use_the_test_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _use_the_test_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    app.dependency_overrides.clear()


@dataclass
class World:
    """One campaign with all three roles signed in, which most API tests need."""

    county: "County"
    constituency: "Constituency"
    ward: "Ward"
    other_ward: "Ward"
    centre: "RegistrationCentre"
    campaign: "Campaign"
    candidate: "User"
    manager: "User"
    mobilizer_user: "User"
    mobilizer: "Mobilizer"
    tokens: dict[str, str]

    def headers(self, role: str) -> dict[str, str]:
        return {"Authorization": f"Token {self.tokens[role]}"}


@pytest.fixture
async def world(session: AsyncSession, client: httpx.AsyncClient) -> World:
    """Roysambu MP: two wards, one staffed by a mobilizer, targets already built."""
    from backend.models import (
        Campaign,
        Constituency,
        County,
        Mobilizer,
        OfficeLevel,
        RegistrationCentre,
        UserRole,
        Ward,
    )
    from backend.services.targets import generate_targets
    from tests.factories import make_user, sign_in

    county = County(
        name="Nairobi City",
        code="047",
        registered_voters=2_400_000,
        turnout_2022_pct=Decimal("60.00"),
    )
    constituency = Constituency(county=county, name="Roysambu", code="279")
    ward = Ward(constituency=constituency, name="Zimmerman", code="1393", registered_voters=30_701)
    other_ward = Ward(
        constituency=constituency, name="Githurai", code="1391", registered_voters=35_899
    )
    centre = RegistrationCentre(
        ward=ward, name="Zimmerman Primary", code="001", registered_voters=2_500
    )
    session.add_all([county, ward, other_ward, centre])
    await session.commit()

    candidate = await make_user(session, username="jane", role=UserRole.CANDIDATE)
    manager = await make_user(session, username="amina", role=UserRole.MANAGER)
    mobilizer_user = await make_user(session, username="juma", role=UserRole.MOBILIZER)

    campaign = Campaign(
        candidate=candidate,
        title="Jane for Roysambu",
        office_level=OfficeLevel.CONSTITUENCY,
        constituency_id=constituency.id,
    )
    session.add(campaign)
    await session.commit()
    await generate_targets(session, campaign)

    mobilizer = Mobilizer(
        campaign=campaign, ward=ward, full_name="Juma Otieno", user=mobilizer_user
    )
    session.add(mobilizer)
    await session.commit()

    tokens = {
        "candidate": await sign_in(client, "jane"),
        "manager": await sign_in(client, "amina"),
        "mobilizer": await sign_in(client, "juma"),
    }
    return World(
        county=county,
        constituency=constituency,
        ward=ward,
        other_ward=other_ward,
        centre=centre,
        campaign=campaign,
        candidate=candidate,
        manager=manager,
        mobilizer_user=mobilizer_user,
        mobilizer=mobilizer,
        tokens=tokens,
    )
