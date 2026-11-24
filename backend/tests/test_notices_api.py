"""Notices under the bell: who gets one for a team sign-up or a payment to approve, and the read
history."""

import secrets

import httpx
import pytest
import requests
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import PushSubscription
from backend.services import push
from tests.conftest import World
from tests.test_payments_api import _schedule, _work
from tests.test_team_signup_api import _sign_up


async def _notices(client: httpx.AsyncClient, world: World, role: str) -> list[dict]:
    return (await client.get("/api/notices/", headers=world.headers(role))).json()


async def test_a_team_sign_up_tells_the_candidate_and_manager_but_not_the_mobilizer(
    client: httpx.AsyncClient, world: World
) -> None:
    assert (await _sign_up(client, world)).status_code == 201

    manager, candidate = (
        await _notices(client, world, "manager"),
        await _notices(client, world, "candidate"),
    )

    assert [(n["text"], n["url"], n["read_at"]) for n in manager] == [
        ("Team sign-up waiting: Achieng Otieno", "/campaign/signups", None)
    ]
    assert len(candidate) == 1
    assert await _notices(client, world, "mobilizer") == []


async def test_a_payment_tells_whoever_approves_it_who_scheduled_it_and_for_what(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    work = await _work(session, world)
    await _schedule(client, world, work)

    (notice,) = await _notices(client, world, "candidate")

    assert notice["text"].startswith(f"Payment to approve: KES {work.amount_kes:,} to ")
    assert notice["sender"] == world.manager.display_name
    assert notice["detail"] == work.label
    assert await _notices(client, world, "manager") == []


async def test_read_notices_stay_as_history_and_read_all_marks_every_one(
    client: httpx.AsyncClient, world: World
) -> None:
    await _sign_up(client, world)
    second = await _sign_up(
        client, world, phone="0712 345002", email="b@example.test", id_number="23456789"
    )
    assert second.status_code == 201, second.text
    first, second = await _notices(client, world, "manager")
    head = world.headers("manager")

    await client.post(f"/api/notices/{first['id']}/read/", headers=head)
    after_one = await _notices(client, world, "manager")
    await client.post("/api/notices/read-all/", headers=head)
    after_all = await _notices(client, world, "manager")

    assert [n["read_at"] is None for n in after_one] == [False, True]
    assert len(after_all) == 2 and all(n["read_at"] for n in after_all)


async def test_an_unreachable_push_service_never_fails_the_sign_up_that_caused_the_notice(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    monkeypatch: pytest.MonkeyPatch,
    fresh_settings: None,
) -> None:
    for name in ("PUBLIC_KEY", "PRIVATE_KEY"):
        monkeypatch.setenv(f"VAPID_{name}", secrets.token_urlsafe(16))
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:office@example.test")
    session.add(
        PushSubscription(
            user_id=world.manager.id,
            endpoint="https://fcm.googleapis.com/x",
            p256dh=secrets.token_urlsafe(16),
            auth=secrets.token_urlsafe(16),
        )
    )
    await session.commit()

    def unreachable(*_):
        raise requests.exceptions.ConnectionError("push service down")

    monkeypatch.setattr(push, "_send", unreachable)

    signed = await _sign_up(client, world)

    assert signed.status_code == 201, signed.text
    assert len(await _notices(client, world, "manager")) == 1
