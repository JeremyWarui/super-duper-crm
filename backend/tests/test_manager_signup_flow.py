"""A manager signs up and sets a campaign up for a new aspirant, on the migrated schema."""

import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from tests.conftest import app_client, enforce_foreign_keys, upgrade_head
from tests.factories import auth, fresh_password, make_geography, members_of


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


async def test_a_manager_signs_up_and_sets_a_campaign_up_for_a_new_aspirant(migrated) -> None:
    client, session = migrated
    county, constituency, _ward, _centre = await make_geography(session)
    county.turnout_2022_pct = Decimal("60.00")
    await session.commit()

    reply = await client.post(
        "/api/auth/register/",
        json={"username": "newmanager", "password": fresh_password(), "role": "manager"},
    )
    assert reply.status_code == 201, reply.text
    head = auth(reply.json()["token"])
    assert (await client.get("/api/campaigns/", headers=head)).json() == []

    body = {
        "title": "Wanjiku for Parklands",
        "office_level": "constituency",
        "constituency": str(constituency.id),
        "election_date": "2027-08-10",
    }
    refused = await client.post("/api/campaigns/setup/", headers=head, json=body)
    assert refused.status_code == 400
    assert refused.json()["detail"].startswith("Say who this campaign is for")

    made = await client.post(
        "/api/campaigns/setup/",
        headers=head,
        json={**body, "new_candidate": {"username": "wanjiku", "first_name": "Mary"}},
    )
    assert made.status_code == 201, made.text
    assert made.json()["setup"]["win_number"] > 0
    assert await members_of(session, uuid.UUID(made.json()["id"])) == {
        "wanjiku": "candidate",
        "newmanager": "manager",
    }

    signed_in = await client.post(
        "/api/auth/login/",
        json={"username": "wanjiku", "password": made.json()["candidate_login"]["password"]},
    )
    assert signed_in.status_code == 200, signed_in.text
    for headers in (head, auth(signed_in.json()["token"])):
        listed = (await client.get("/api/campaigns/", headers=headers)).json()
        assert [c["title"] for c in listed] == ["Wanjiku for Parklands"]
