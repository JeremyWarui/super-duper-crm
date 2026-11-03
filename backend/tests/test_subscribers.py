"""The website footer's news sign-up, its unsubscribe link, and the demo Contribute form."""

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.base import Base
from backend.models import PartySettings, Subscriber
from backend.services.consent import SUBSCRIBE_WORDING


@pytest.fixture(autouse=True)
async def settings_row(session: AsyncSession) -> None:
    session.add(PartySettings(name="Party name", privacy_notice_version="2026-11"))
    await session.commit()


async def test_a_sign_up_stores_its_consent_and_answers_the_same_twice(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    body = {"contact": "0712 345678", "consent_given": True}
    first = await client.post("/api/party/subscribe/", json=body)
    again = await client.post("/api/party/subscribe/", json=body)

    assert first.status_code == again.status_code == 201
    assert first.json()["message"] == again.json()["message"]
    row = (await session.scalars(select(Subscriber))).one()
    assert (row.contact, row.channel) == ("+254712345678", "sms")
    assert row.consent_wording == SUBSCRIBE_WORDING
    assert row.notice_version == "2026-11"
    assert row.created_at is not None


async def test_its_link_unsubscribes_and_any_code_gets_the_same_answer(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    done = await client.post(
        "/api/party/subscribe/", json={"contact": "Ama@Example.com", "consent_given": True}
    )
    code = done.json()["unsubscribe_url"].rsplit("/", 1)[-1]

    unknown = await client.post("/api/party/unsubscribe/not-a-real-code/")
    known = await client.post(f"/api/party/unsubscribe/{code}/")

    assert unknown.json() == known.json()
    assert await session.scalar(select(func.count()).select_from(Subscriber)) == 0


async def test_contribute_says_it_is_a_demo_and_stores_nothing(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    async def rows() -> int:
        total = 0
        for table in Base.metadata.sorted_tables:
            total += await session.scalar(select(func.count()).select_from(table))
        return total

    before = await rows()
    response = await client.post(
        "/api/party/contribute/",
        json={"amount_kes": 500, "name": "Ama Otieno", "phone": "0712345678", "consent_given": True},
    )

    assert response.status_code == 200
    assert response.json()["demo"] is True
    assert "no money moved" in response.json()["message"]
    assert await rows() == before
