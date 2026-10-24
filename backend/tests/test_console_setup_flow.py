"""The superuser sets a campaign up from the console, on the migrated schema."""

import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.models import UserRole
from tests.conftest import app_client, enforce_foreign_keys, upgrade_head
from tests.factories import auth, make_geography, make_user, members_of, sign_in


@pytest.fixture
async def migrated(tmp_path):
    """The app on a SQLite file built by the migrations."""
    db = tmp_path / "e2e.sqlite3"
    sync = sa.create_engine(f"sqlite:///{db.as_posix()}")
    with sync.begin() as connection:
        upgrade_head(connection)
    sync.dispose()
    engine = enforce_foreign_keys(create_async_engine(f"sqlite+aiosqlite:///{db.as_posix()}"))
    async with (
        AsyncSession(engine, expire_on_commit=False) as session,
        app_client(session) as client,
    ):
        yield client, session
    await engine.dispose()


async def test_the_superuser_sets_a_campaign_up_that_its_aspirant_and_manager_work_on(
    migrated,
) -> None:
    client, session = migrated
    county, constituency, _ward, _centre = await make_geography(session)
    county.turnout_2022_pct = Decimal("60.00")
    root = await make_user(session, username="root", role=UserRole.MANAGER)
    root.is_superuser = True
    await session.commit()

    made = await client.post(
        "/api/admin/campaigns/",
        headers=auth(await sign_in(client, "root")),
        json={
            "title": "Wanjiku for Parklands",
            "seat": "mp",
            "constituency": str(constituency.id),
            "election_date": "2027-08-10",
            "aspirant": {"username": "wanjiku", "first_name": "Mary"},
            "manager": {"username": "otieno"},
        },
    )

    assert made.status_code == 201, made.text
    body = made.json()
    assert body["setup"]["win_number"] > 0
    assert await members_of(session, uuid.UUID(body["campaign"]["id"])) == {
        "wanjiku": "candidate",
        "otieno": "manager",
    }
    for login in body["logins"]:
        head = auth(await sign_in(client, login["username"], login["password"]))
        listed = (await client.get("/api/campaigns/", headers=head)).json()
        assert [c["title"] for c in listed] == ["Wanjiku for Parklands"]
