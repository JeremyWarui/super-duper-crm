"""The party demo install: one run sets up an empty database with every sign-in working."""

from datetime import date

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.seed.demo_party import build_party
from backend.seed.reference import import_geography
from backend.services.errors import Refused
from tests.factories import auth, fresh_password

pytestmark = pytest.mark.party_only


async def test_the_party_demo_signs_everyone_in_with_work_waiting(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await import_geography(session)
    password = fresh_password()

    # The CLI's sessions never autoflush.
    async with AsyncSession(session.bind, expire_on_commit=False, autoflush=False) as cli:
        sign_ins = await build_party(cli, password=password, today=date(2026, 11, 1))

    tokens = {}
    for s in sign_ins:
        answer = await client.post(
            "/api/auth/login/", json={"email": s.email, "password": password}
        )
        assert answer.status_code == 200, (s.email, answer.text)
        tokens[s.email.split("@")[0]] = answer.json()["token"]
    assert {"admin", "membership", "nominations", "comms", "aspirant", "manager"} <= set(tokens)

    members = (await client.get("/api/party/members/", headers=auth(tokens["membership"]))).json()
    statuses = {m["status"] for m in members["items"]}
    assert {"approved", "pending"} <= statuses
    aspirants = (
        await client.get("/api/party/aspirants/", headers=auth(tokens["nominations"]))
    ).json()
    assert {a["status"] for a in aspirants["items"]} >= {"approved", "submitted"}
    candidates = (await client.get("/api/candidates/")).json()
    assert "Jane Wanjiru" in {c["name"] for c in candidates}
    agenda = (await client.get("/api/party/issues/")).json()
    assert len(agenda) == 6
    assert all(i["image_url"].startswith("https://") for i in agenda)
    campaigns = await client.get("/api/campaigns/", headers=auth(tokens["aspirant"]))
    assert [c["title"] for c in campaigns.json()] == ["Jane for Roysambu"]


async def test_the_party_demo_refuses_a_database_already_set_up(session: AsyncSession) -> None:
    await import_geography(session)
    await build_party(session, password=fresh_password(), today=date(2026, 11, 1))

    with pytest.raises(Refused):
        await build_party(session, password=fresh_password(), today=date(2026, 11, 1))
