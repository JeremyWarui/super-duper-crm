"""The whole sign-up flow for a campaign manager, on a database built by the migrations.

Every other API test builds its schema with `create_all` and its world with a
fixture. This one walks the path a real manager walks, against the migrated
schema, on a database that already holds a campaign belonging to somebody else.
"""

import importlib.util
import uuid
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

VERSIONS = sorted((Path(__file__).resolve().parent.parent / "alembic" / "versions").glob("*.py"))


def _load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build(db, *, stop_before=None):
    """Run the migrations into `db`, optionally stopping before one revision."""
    sync = sa.create_engine(f"sqlite:///{db.as_posix()}")
    with sync.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        for path in VERSIONS:
            module = _load(path)
            if stop_before is not None and module.revision == stop_before:
                break
            module.upgrade()
    sync.dispose()


def _apply(db, revision):
    """Run one revision against an already-migrated database."""
    path = next(p for p in VERSIONS if _load(p).revision == revision)
    sync = sa.create_engine(f"sqlite:///{db.as_posix()}")
    with sync.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        _load(path).upgrade()
    sync.dispose()


def _client_on(db):
    """The real app on an already-migrated database file."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{db.as_posix()}")

    @sa.event.listens_for(engine.sync_engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


async def _legacy_campaign(session, *, candidate_id, title, ward_id) -> uuid.UUID:
    """A campaign row as it was stored before `campaign_members` named the candidate."""
    campaign_id = uuid.uuid4()
    await session.execute(
        sa.text(
            "INSERT INTO campaigns (id, candidate_id, title, office_level, ward_id, created_at) "
            "VALUES (:id, :candidate, :title, 'ward', :ward, CURRENT_TIMESTAMP)"
        ),
        {"id": campaign_id.hex, "candidate": candidate_id.hex, "title": title, "ward": ward_id.hex},
    )
    return campaign_id


@pytest.fixture
async def migrated_client(tmp_path):
    """The real app on a database built by the migrations, not by create_all."""
    db = tmp_path / "e2e.sqlite3"
    sync = sa.create_engine(f"sqlite:///{db.as_posix()}")
    with sync.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        for path in VERSIONS:
            _load(path).upgrade()
    sync.dispose()

    engine = create_async_engine(f"sqlite+aiosqlite:///{db.as_posix()}")

    # SQLite ignores foreign keys unless this is on, and this file exists to
    # check what the migrated keys actually do.
    @sa.event.listens_for(engine.sync_engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    from backend.db.session import get_session
    from backend.main import app

    async with AsyncSession(engine, expire_on_commit=False) as session:

        async def _use_it():
            yield session

        app.dependency_overrides[get_session] = _use_it
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://e2e") as client:
            yield client, session
        app.dependency_overrides.clear()
    await engine.dispose()


async def test_a_manager_signs_up_and_stands_a_campaign_up_for_an_aspirant(
    migrated_client, monkeypatch
) -> None:
    from backend.config import get_settings
    from backend.models import Campaign, CampaignMember, OfficeLevel, User, UserRole
    from backend.security import hash_password

    monkeypatch.setenv("ALLOW_REGISTRATION", "true")
    get_settings.cache_clear()
    client, session = migrated_client

    # Somebody else's campaign already exists, which is what used to hide setup.
    from tests.factories import make_geography

    county, constituency, ward, _centre = await make_geography(session)
    county.turnout_2022_pct = Decimal("60.00")
    stranger = User(username="stranger", role=UserRole.CANDIDATE, password_hash=hash_password("x"))
    session.add(stranger)
    await session.flush()
    session.add(
        Campaign(
            title="Somebody Else For Something",
            office_level=OfficeLevel.WARD,
            ward_id=ward.id,
        )
    )
    await session.commit()

    reply = await client.post(
        "/api/auth/register/",
        json={"username": "newmanager", "password": "a-long-enough-password", "role": "manager"},
    )
    assert reply.status_code == 201, reply.text
    head = {"Authorization": f"Token {reply.json()['token']}"}

    # The two calls the browser makes to decide what to show.
    assert (await client.get("/api/campaigns/", headers=head)).json() == []
    assert (await client.get("/api/users/?role=candidate", headers=head)).json() == []

    refused = await client.post(
        "/api/campaigns/setup/",
        headers=head,
        json={
            "title": "Wanjiku for Parklands",
            "office_level": "constituency",
            "constituency": str(constituency.id),
        },
    )
    assert refused.status_code == 400
    assert refused.json()["detail"].startswith("Say who this campaign is for")

    made = await client.post(
        "/api/campaigns/setup/",
        headers=head,
        json={
            "title": "Wanjiku for Parklands",
            "office_level": "constituency",
            "constituency": str(constituency.id),
            "election_date": "2027-08-10",
            "new_candidate": {"username": "wanjiku", "first_name": "Mary", "last_name": "Wanjiku"},
        },
    )
    assert made.status_code == 201, made.text
    body = made.json()
    assert body["setup"]["win_number"] > 0

    members = await session.execute(
        sa.select(User.username, CampaignMember.role)
        .join(CampaignMember, CampaignMember.user_id == User.id)
        .where(CampaignMember.campaign_id == uuid.UUID(body["id"]))
    )
    assert {u: r.value for u, r in members} == {"wanjiku": "candidate", "newmanager": "manager"}
    aspirant_login = body["candidate_login"]

    assert [c["title"] for c in (await client.get("/api/campaigns/", headers=head)).json()] == [
        "Wanjiku for Parklands"
    ]

    signed_in = await client.post(
        "/api/auth/login/",
        json={"username": "wanjiku", "password": aspirant_login["password"]},
    )
    assert signed_in.status_code == 200, signed_in.text
    aspirant_head = {"Authorization": f"Token {signed_in.json()['token']}"}
    assert [
        c["title"] for c in (await client.get("/api/campaigns/", headers=aspirant_head)).json()
    ] == ["Wanjiku for Parklands"]

    get_settings.cache_clear()


async def test_the_migrated_schema_keeps_the_campaign_when_a_member_goes(
    migrated_client,
) -> None:
    """`create_all` and the migration must agree about ondelete, not just columns."""
    from backend.api.scope import add_member
    from backend.models import Campaign, CampaignMember, OfficeLevel, User, UserRole
    from backend.security import hash_password
    from tests.factories import make_geography

    client, session = migrated_client
    _county, _constituency, ward, _centre = await make_geography(session)

    candidate = User(username="jane", role=UserRole.CANDIDATE, password_hash=hash_password("x"))
    manager = User(username="amina", role=UserRole.MANAGER, password_hash=hash_password("x"))
    session.add_all([candidate, manager])
    await session.flush()
    campaign = Campaign(
        title="Jane for Parklands",
        office_level=OfficeLevel.WARD,
        ward_id=ward.id,
    )
    session.add(campaign)
    await session.flush()
    await add_member(session, campaign.id, candidate.id)
    await add_member(session, campaign.id, manager.id)
    await session.commit()

    # Losing a member takes their row and nothing else.
    await session.delete(manager)
    await session.commit()
    assert (
        await session.scalar(sa.select(Campaign.id).where(Campaign.id == campaign.id)) is not None
    )
    left = (
        await session.execute(
            sa.select(CampaignMember.user_id).where(CampaignMember.campaign_id == campaign.id)
        )
    ).scalars()
    assert list(left) == [candidate.id]

    # The candidate is a member too; the API refuses the delete, the schema keeps the campaign.
    await session.delete(await session.get(User, candidate.id))
    await session.commit()
    assert (
        await session.scalar(sa.select(Campaign.id).where(Campaign.id == campaign.id)) is not None
    )
    assert (
        await session.scalar(
            sa.select(CampaignMember.id).where(CampaignMember.campaign_id == campaign.id)
        )
    ) is None


async def test_the_backfill_puts_an_existing_deployment_back_on_its_campaigns(
    tmp_path,
) -> None:
    """A campaign that predates `campaign_members` stays visible to its people."""
    from backend.db.session import get_session
    from backend.main import app
    from backend.models import Mobilizer, User, UserRole
    from backend.security import hash_password
    from tests.factories import make_geography

    backfill = "c3d4e5f6a7b8"
    db = tmp_path / "old.sqlite3"
    _build(db, stop_before=backfill)

    engine = _client_on(db)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        _county, _constituency, ward, _centre = await make_geography(session)
        jane = User(
            username="jane",
            role=UserRole.CANDIDATE,
            password_hash=hash_password("a-long-enough-password"),
        )
        boots = User(
            username="boots",
            role=UserRole.MOBILIZER,
            password_hash=hash_password("a-long-enough-password"),
        )
        session.add_all([jane, boots])
        await session.flush()
        campaign_id = await _legacy_campaign(
            session, candidate_id=jane.id, title="Jane for Zimmerman", ward_id=ward.id
        )
        session.add(
            Mobilizer(
                campaign_id=campaign_id,
                ward_id=ward.id,
                user_id=boots.id,
                full_name="Boots On Ground",
                phone="+254700111222",
            )
        )
        await session.commit()

        # Before the backfill nobody is on it, which is the state that would
        # ship to a live deployment.
        rows = await session.execute(sa.text("SELECT COUNT(*) FROM campaign_members"))
        assert rows.scalar_one() == 0
    await engine.dispose()

    _apply(db, backfill)

    engine = _client_on(db)
    async with AsyncSession(engine, expire_on_commit=False) as session:

        async def _use_it():
            yield session

        app.dependency_overrides[get_session] = _use_it
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://e2e") as client:
            for who in ("jane", "boots"):
                signed_in = await client.post(
                    "/api/auth/login/",
                    json={"username": who, "password": "a-long-enough-password"},
                )
                assert signed_in.status_code == 200, signed_in.text
                seen = await client.get(
                    "/api/campaigns/",
                    headers={"Authorization": f"Token {signed_in.json()['token']}"},
                )
                assert [c["title"] for c in seen.json()] == ["Jane for Zimmerman"], who
        app.dependency_overrides.clear()
    await engine.dispose()


async def test_the_backfill_can_be_run_twice_without_doubling_anybody(tmp_path) -> None:
    db = tmp_path / "twice.sqlite3"
    _build(db, stop_before="c3d4e5f6a7b8")

    engine = _client_on(db)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        from backend.models import User, UserRole
        from backend.security import hash_password
        from tests.factories import make_geography

        _county, _constituency, ward, _centre = await make_geography(session)
        jane = User(username="jane", role=UserRole.CANDIDATE, password_hash=hash_password("x"))
        session.add(jane)
        await session.flush()
        await _legacy_campaign(
            session, candidate_id=jane.id, title="Jane for Zimmerman", ward_id=ward.id
        )
        await session.commit()
    await engine.dispose()

    _apply(db, "c3d4e5f6a7b8")
    _apply(db, "c3d4e5f6a7b8")

    sync = sa.create_engine(f"sqlite:///{db.as_posix()}")
    with sync.begin() as connection:
        rows = connection.execute(sa.text("SELECT COUNT(*) FROM campaign_members")).scalar_one()
    sync.dispose()

    assert rows == 1


async def test_the_backfill_reads_the_role_off_the_login_not_the_row_it_found_them_on(
    tmp_path,
) -> None:
    """A ground row could hold any login before this table existed.

    The route that wrote `mobilizers.user_id` never checked the role, so a
    manager's login can sit on one. Calling that membership "mobilizer" would
    hand back the disagreement the table exists to end: every permission check
    reads `users.role`, so they would run the campaign under a quiet name.
    """
    from backend.models import Mobilizer, User, UserRole
    from backend.security import hash_password
    from tests.factories import make_geography

    db = tmp_path / "legacy.sqlite3"
    _build(db, stop_before="c3d4e5f6a7b8")

    engine = _client_on(db)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        _county, _constituency, ward, _centre = await make_geography(session)
        jane = User(username="jane", role=UserRole.CANDIDATE, password_hash=hash_password("x"))
        boss = User(username="boss", role=UserRole.MANAGER, password_hash=hash_password("x"))
        session.add_all([jane, boss])
        await session.flush()
        campaign_id = await _legacy_campaign(
            session, candidate_id=jane.id, title="Jane for Zimmerman", ward_id=ward.id
        )
        session.add(
            Mobilizer(
                campaign_id=campaign_id,
                ward_id=ward.id,
                user_id=boss.id,
                full_name="A Manager On The Ground",
                phone="+254700111222",
            )
        )
        await session.commit()
    await engine.dispose()

    _apply(db, "c3d4e5f6a7b8")

    engine = _client_on(db)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        rows = await session.execute(
            sa.text(
                "SELECT u.username, m.role FROM campaign_members m "
                "JOIN users u ON u.id = m.user_id ORDER BY u.username"
            )
        )
        assert dict(rows.all()) == {"boss": "manager", "jane": "candidate"}
    await engine.dispose()


async def test_the_backfill_skips_a_campaign_whose_candidate_is_gone(tmp_path) -> None:
    """Without the join this either writes an orphan or aborts the migration."""
    db = tmp_path / "dangling.sqlite3"
    _build(db, stop_before="c3d4e5f6a7b8")

    sync = sa.create_engine(f"sqlite:///{db.as_posix()}")
    with sync.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO campaigns (id, candidate_id, title, office_level, created_at) "
                "VALUES (:id, :candidate, 'Ghost', 'ward', CURRENT_TIMESTAMP)"
            ),
            {"id": "a" * 32, "candidate": "b" * 32},
        )
    sync.dispose()

    _apply(db, "c3d4e5f6a7b8")

    sync = sa.create_engine(f"sqlite:///{db.as_posix()}")
    with sync.begin() as connection:
        rows = connection.execute(sa.text("SELECT COUNT(*) FROM campaign_members")).scalar_one()
    sync.dispose()
    assert rows == 0
