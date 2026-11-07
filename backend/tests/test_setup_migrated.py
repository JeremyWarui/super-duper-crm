"""First-run setup makes an aspirant's workspace on the migrated schema."""

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.api.deps import get_organisation_type
from backend.main import app
from backend.services import setup, site
from tests.conftest import app_client, enforce_foreign_keys, upgrade_head
from tests.factories import auth, claim_link, make_geography
from tests.test_setup_api import _request

pytestmark = pytest.mark.party_only


@pytest.fixture
async def migrated(tmp_path):
    """The app on a SQLite file built by the migrations, reading its real organisation type."""
    db = tmp_path / "e2e.sqlite3"
    sync = sa.create_engine(f"sqlite:///{db.as_posix()}")
    with sync.begin() as connection:
        upgrade_head(connection)
    sync.dispose()
    engine = enforce_foreign_keys(create_async_engine(f"sqlite+aiosqlite:///{db.as_posix()}"))
    site._organisation_type = None
    try:
        async with (
            AsyncSession(engine, expire_on_commit=False) as session,
            app_client(session) as client,
        ):
            del app.dependency_overrides[get_organisation_type]
            yield client, session
    finally:
        site._organisation_type = None
        await engine.dispose()


async def test_setup_makes_a_workspace_its_candidate_signs_in_to(migrated) -> None:
    client, session = migrated
    *_, ward, _ = await make_geography(session)
    token = await setup.new_token(session)

    made = await client.post("/api/setup/", json=_request(token, ward.id))

    assert made.status_code == 201, made.text
    head = auth(await claim_link(client, session, "jane@example.com"))
    listed = (await client.get("/api/campaigns/", headers=head)).json()
    assert [c["title"] for c in listed] == ["Jane for Parklands"]
    assert listed[0]["kind"] == "standalone"
