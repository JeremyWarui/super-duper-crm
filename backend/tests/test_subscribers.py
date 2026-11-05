"""The website footer's news sign-up and its unsubscribe link."""

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Subscriber
from backend.services.consent import SUBSCRIBE_WORDING
from tests.factories import site_settings


@pytest.fixture(autouse=True)
async def settings_row(session: AsyncSession) -> None:
    session.add(site_settings(privacy_notice_version="2026-11"))
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
