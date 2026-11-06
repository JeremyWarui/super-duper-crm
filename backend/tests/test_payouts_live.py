"""Live payouts through Paystack, against its recorded replies: the balance gate, the webhook as the
only word on a transfer, and reconciliation with Paystack's own records."""

import copy
import hashlib
import hmac
import json
import secrets
from pathlib import Path

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Assignment, AssignmentKind, AssignmentStatus, Event, EventStatus
from backend.services.payouts import PaystackPayouts
from tests.conftest import World

RECORDED = json.loads((Path(__file__).parent / "fixtures" / "paystack.json").read_text())


class Paystack:
    """Answers as Paystack did, and remembers every path asked for."""

    def __init__(self, balance_cents: int = 1_000_000) -> None:
        self.calls: list[str] = []
        self.balance = copy.deepcopy(RECORDED["balance"])
        self.balance["data"][0]["balance"] = balance_cents
        self.transfers = copy.deepcopy(RECORDED["transfer_list"])

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = f"{request.method} {request.url.path}"
        self.calls.append(path)
        answer = {
            "POST /transferrecipient": RECORDED["recipient"],
            "POST /transfer": RECORDED["transfer_success"],
            "GET /balance": self.balance,
            "GET /transfer": self.transfers,
        }[path]
        return httpx.Response(200, json=answer)


@pytest.fixture
def key(monkeypatch: pytest.MonkeyPatch, fresh_settings: None) -> str:
    value = secrets.token_hex(20)
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", value)
    return value


@pytest.fixture
def paystack(monkeypatch: pytest.MonkeyPatch, key: str) -> Paystack:
    from backend.api.routers import payments
    from backend.services import reconcile

    fake = Paystack()
    provider = PaystackPayouts(key, transport=httpx.MockTransport(fake))
    monkeypatch.setattr(payments, "get_payout_provider", lambda: provider)
    monkeypatch.setattr(reconcile, "get_payout_provider", lambda: provider)
    return fake


async def _scheduled(client: httpx.AsyncClient, session: AsyncSession, world: World, amount=1500):
    world.mobilizer.phone = "0712 345678"
    event = Event(
        campaign_id=world.campaign.id,
        ward_id=world.ward.id,
        title="Zimmerman town hall",
        status=EventStatus.DONE,
    )
    session.add(event)
    await session.flush()
    work = Assignment(
        campaign_id=world.campaign.id,
        kind=AssignmentKind.EVENT,
        event_id=event.id,
        mobilizer_id=world.mobilizer.id,
        amount_kes=amount,
        status=AssignmentStatus.DONE,
    )
    session.add(work)
    await session.commit()
    made = await client.post(
        "/api/payments/", headers=world.headers("manager"), json={"assignment": str(work.id)}
    )
    assert made.status_code == 201, made.text
    return made.json()


async def _webhook(client: httpx.AsyncClient, key: str, kind: str, reference: str):
    body = copy.deepcopy(RECORDED[kind])
    body["data"]["reference"] = reference
    raw = json.dumps(body).encode()
    signature = hmac.new(key.encode(), raw, hashlib.sha512).hexdigest()
    return await client.post(
        "/api/payments/paystack/webhook/",
        content=raw,
        headers={"x-paystack-signature": signature, "content-type": "application/json"},
    )


async def _payment(client: httpx.AsyncClient, world: World) -> dict:
    return (await client.get("/api/payments/", headers=world.headers("candidate"))).json()[0]


async def test_only_the_webhook_marks_a_transfer_paid_and_a_repeat_changes_nothing(
    client: httpx.AsyncClient, session: AsyncSession, world: World, paystack: Paystack, key: str
) -> None:
    made = await _scheduled(client, session, world)
    head = world.headers("candidate")

    released = (await client.post(f"/api/payments/{made['id']}/release/", headers=head)).json()
    reference = f"pay-{made['id']}-1"
    first = await _webhook(client, key, "webhook_success", reference)
    paid = await _payment(client, world)
    repeat = await _webhook(client, key, "webhook_success", reference)

    assert released["status"] == "sending"
    assert first.json()["applied"] is True
    assert paid["status"] == "paid"
    assert repeat.json()["applied"] is True
    assert await _payment(client, world) == paid


async def test_a_reversed_transfer_returns_to_retry_with_the_reason(
    client: httpx.AsyncClient, session: AsyncSession, world: World, paystack: Paystack, key: str
) -> None:
    made = await _scheduled(client, session, world)
    await client.post(f"/api/payments/{made['id']}/release/", headers=world.headers("candidate"))
    reference = f"pay-{made['id']}-1"
    await _webhook(client, key, "webhook_success", reference)

    await _webhook(client, key, "webhook_reversed", reference)
    reversed_ = await _payment(client, world)

    assert reversed_["status"] == "failed"
    assert reversed_["failure_reason"] == (
        "Paystack says the transfer reversed. Recipient wallet limit reached"
    )
    assert reversed_["paid_at"] is None


async def test_a_release_the_balance_does_not_cover_is_refused_before_any_transfer(
    client: httpx.AsyncClient, session: AsyncSession, world: World, paystack: Paystack
) -> None:
    paystack.balance["data"][0]["balance"] = 150_000  # KES 1,500, short of the KES 20 fee
    made = await _scheduled(client, session, world, amount=1500)
    head = world.headers("candidate")

    check = await client.post(
        "/api/payments/release-check/", headers=head, json={"payments": [made["id"]]}
    )
    refused = await client.post(f"/api/payments/{made['id']}/release/", headers=head)

    assert check.json() == {
        "mode": "paystack",
        "moves_money": True,
        "balance_kes": 1500,
        "amount_kes": 1500,
        "fee_kes": 20,
        "left_kes": -20,
        "enough": False,
    }
    assert refused.status_code == 400
    assert "KES 1,520" in refused.json()["detail"]
    assert [c for c in paystack.calls if c != "GET /balance"] == []
    assert (await _payment(client, world))["status"] == "scheduled"


async def test_reconciliation_lists_a_planted_difference(
    client: httpx.AsyncClient, session: AsyncSession, world: World, paystack: Paystack, key: str
) -> None:
    made = await _scheduled(client, session, world)
    head = world.headers("candidate")
    await client.post(f"/api/payments/{made['id']}/release/", headers=head)
    reference = f"pay-{made['id']}-1"
    await _webhook(client, key, "webhook_success", reference)
    paystack.transfers["data"][0]["reference"] = reference  # Paystack's own record: failed

    path = f"/api/payments/reconciliation/?campaign={world.campaign.id}"
    ran = (await client.post(path, headers=head)).json()

    assert (ran["last_run"]["status"], ran["last_run"]["checked"]) == ("differences", 1)
    assert [
        (d["recipient_name"], d["ledger"], d["provider"], d["detail"]) for d in ran["differences"]
    ] == [
        (
            made["recipient_name"],
            "paid",
            "failed",
            "Marked paid here, but Paystack shows the transfer did not go through.",
        )
    ]


async def test_practice_mode_moves_no_money_and_has_nothing_to_reconcile(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    made = await _scheduled(client, session, world)
    head = world.headers("candidate")

    check = (
        await client.post(
            "/api/payments/release-check/", headers=head, json={"payments": [made["id"]]}
        )
    ).json()
    ran = (
        await client.post(
            f"/api/payments/reconciliation/?campaign={world.campaign.id}", headers=head
        )
    ).json()

    assert (check["moves_money"], check["fee_kes"], check["enough"]) == (False, 0, True)
    assert (ran["last_run"]["status"], ran["differences"]) == ("practice", [])
