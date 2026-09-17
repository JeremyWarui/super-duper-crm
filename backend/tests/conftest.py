"""Fixtures: an in-memory database from the models, the app on it, and a seeded campaign."""

import os
import secrets
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

import httpx
import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

os.environ.setdefault("SECRET_KEY", secrets.token_urlsafe(48))
# Overrides a developer's .env, so the suite always exercises the generated password.
os.environ["DEFAULT_USER_PASSWORD"] = ""

from backend.models import Base  # noqa: E402

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
    """Hash with minimal Argon2 cost; the real parameters are checked in test_security.py."""
    from argon2 import PasswordHasher

    import backend.security as security

    real = security._hasher
    security._hasher = PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1)
    yield
    security._hasher = real


@pytest.fixture
def fresh_settings() -> Iterator[None]:
    """Re-read the environment either side of the test."""
    from backend.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def enforce_foreign_keys(engine: AsyncEngine) -> AsyncEngine:
    """Turn on SQLite's foreign keys for every connection the engine opens."""

    @event.listens_for(engine.sync_engine, "connect")
    def _on(dbapi_connection, _record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


@asynccontextmanager
async def app_client(session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    """The real app, serving every request from this session."""
    from backend.db.session import get_session
    from backend.main import app

    async def _use_it() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _use_it
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    app.dependency_overrides.clear()


def revision_modules() -> list:
    """Every Alembic revision module, loaded, in file order."""
    import importlib.util
    from pathlib import Path

    modules = []
    for path in sorted((Path(__file__).parent.parent / "alembic" / "versions").glob("*.py")):
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules.append(module)
    return modules


def upgrade_head(connection) -> None:
    """Apply every revision on a synchronous connection."""
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with Operations.context(MigrationContext.configure(connection)):
        for module in revision_modules():
            module.upgrade()


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    engine = enforce_foreign_keys(create_async_engine("sqlite+aiosqlite://"))
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    async with app_client(session) as http_client:
        yield http_client


@dataclass
class World:
    """One campaign with a candidate, manager and mobilizer, each signed in."""

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
    """Roysambu MP: two wards, Zimmerman staffed by a mobilizer, targets built."""
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
    from backend.services.accounts import add_member
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
        title="Jane for Roysambu",
        office_level=OfficeLevel.CONSTITUENCY,
        constituency_id=constituency.id,
    )
    session.add(campaign)
    await session.flush()
    for member in (candidate, manager, mobilizer_user):
        await add_member(session, campaign.id, member)
    await generate_targets(session, campaign)
    await session.commit()

    mobilizer = Mobilizer(
        campaign=campaign, ward=ward, full_name="Juma Otieno", user=mobilizer_user
    )
    session.add(mobilizer)
    await session.commit()

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
        tokens={
            "candidate": await sign_in(client, "jane"),
            "manager": await sign_in(client, "amina"),
            "mobilizer": await sign_in(client, "juma"),
        },
    )


@pytest.fixture
async def admin_headers(session: AsyncSession, client: httpx.AsyncClient) -> dict[str, str]:
    """A signed-in superuser, `root`."""
    from backend.models import UserRole
    from tests.factories import auth, make_user, sign_in

    root = await make_user(session, username="root", role=UserRole.MANAGER)
    root.is_superuser = True
    await session.commit()
    return auth(await sign_in(client, "root"))


@pytest.fixture
async def new_manager(client: httpx.AsyncClient, session: AsyncSession, world: World) -> dict:
    """A manager on no campaign yet, signed in as `newmanager`."""
    from backend.models import UserRole
    from tests.factories import auth, make_user, sign_in

    await make_user(session, username="newmanager", role=UserRole.MANAGER)
    return auth(await sign_in(client, "newmanager"))


@pytest.fixture
async def new_candidate(client: httpx.AsyncClient, session: AsyncSession, world: World) -> dict:
    """An aspirant on no campaign yet, signed in as `newaspirant`."""
    from backend.models import UserRole
    from tests.factories import auth, make_user, sign_in

    await make_user(session, username="newaspirant", role=UserRole.CANDIDATE)
    return auth(await sign_in(client, "newaspirant"))
