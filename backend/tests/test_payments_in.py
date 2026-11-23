"""Contributing by M-Pesa: a prompt (practice, or Paystack with its webhook) or a Paybill code
the campaign confirms."""

import hashlib
import hmac
import json
import secrets

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    PayInMethod,
    PayInStatus,
    PaymentIn,
)
from backend.services import payments_in
from backend.services.payments_in import PaystackPayIns
from tests.conftest import World
from tests.factories import site_settings

CONTRIBUTE = "/api/pay/contribution/"
GIFT = {"amount_kes": 500, "name": "Wanjiru Kamau", "phone": "0712 345678"}


@pytest.fixture
async def site(session: AsyncSession) -> None:
    session.add(
        site_settings(
            contact_email="office@example.com",
            mpesa_paybill="123456",
            mpesa_account="DONATE",
        )
    )
    await session.commit()


class Paystack:
    """Answers the Charge API as Paystack documents it, and remembers what was asked."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            self.sent.append(json.loads(request.content))
            return httpx.Response(200, json={"status": True, "data": {"status": "pay_offline"}})
        return httpx.Response(200, json={"status": True, "data": {"status": "pending"}})


@pytest.fixture
def paystack(monkeypatch: pytest.MonkeyPatch, fresh_settings: None) -> tuple[Paystack, str]:
    key = secrets.token_hex(20)
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", key)
    monkeypatch.setenv("PAYIN_PROVIDER", "paystack")
    fake = Paystack()
    provider = PaystackPayIns(key, transport=httpx.MockTransport(fake))
    monkeypatch.setattr(payments_in, "get_payin_provider", lambda: provider)
    return fake, key


async def _webhook(client: httpx.AsyncClient, key: str, data: dict) -> httpx.Response:
    raw = json.dumps({"event": "charge.success", "data": data}).encode()
    signature = hmac.new(key.encode(), raw, hashlib.sha512).hexdigest()
    return await client.post(
        "/api/payments/paystack/webhook/",
        content=raw,
        headers={"x-paystack-signature": signature, "content-type": "application/json"},
    )


async def test_a_practice_prompt_pays_a_contribution_to_the_campaign_at_once(
    client: httpx.AsyncClient, session: AsyncSession, world: World, site: None
) -> None:
    made = await client.post(CONTRIBUTE, json={**GIFT, "method": "stk"})
    seen = await client.get(f"/api/pay/{made.json()['reference']}/")

    assert made.status_code == 201, made.text
    assert (seen.json()["status"], seen.json()["practice"]) == ("paid", True)
    row = await session.scalar(select(PaymentIn))
    assert (row.campaign_id, row.payer_phone, row.amount_kes) == (
        world.campaign.id,
        "+254712345678",
        500,
    )


async def test_a_paybill_code_waits_for_the_office_and_is_taken_once(
    client: httpx.AsyncClient, site: None
) -> None:
    body = {**GIFT, "method": "manual", "mpesa_code": "skl7q2m9xa"}
    first = await client.post(CONTRIBUTE, json=body)
    again = await client.post(CONTRIBUTE, json=body)
    bad = await client.post(CONTRIBUTE, json={**body, "mpesa_code": "123"})

    assert first.json()["status"] == "to_confirm"
    assert (again.status_code, again.json()["detail"]) == (
        400,
        "That M-Pesa code is already recorded.",
    )
    assert "10 letters and numbers" in bad.json()["detail"]


async def test_only_a_signed_matching_paystack_charge_marks_a_prompt_paid(
    client: httpx.AsyncClient, session: AsyncSession, site: None, paystack
) -> None:
    fake, key = paystack
    made = (await client.post(CONTRIBUTE, json={**GIFT, "method": "stk"})).json()
    reference = made["reference"]
    charge = {"reference": reference, "status": "success", "amount": 50000, "currency": "KES"}

    forged = await client.post(
        "/api/payments/paystack/webhook/",
        content=json.dumps({"event": "charge.success", "data": charge}),
        headers={"x-paystack-signature": "0" * 128},
    )
    applied = await _webhook(client, key, {**charge, "receipt_number": "SKL7Q2M9XA"})
    replay = await _webhook(client, key, charge)

    assert made["status"] == "pending"
    sent = fake.sent[0]
    assert (sent["amount"], sent["currency"], sent["mobile_money"]) == (
        "50000",
        "KES",
        {"phone": "+254712345678", "provider": "mpesa"},
    )
    assert forged.status_code == 401
    assert (applied.json(), replay.json()) == ({"applied": True}, {"applied": False})
    row = await session.scalar(select(PaymentIn).execution_options(populate_existing=True))
    assert (row.status, row.mpesa_code) == (PayInStatus.PAID, "SKL7Q2M9XA")


async def test_a_paystack_charge_for_the_wrong_amount_fails_the_payment(
    client: httpx.AsyncClient, session: AsyncSession, site: None, paystack
) -> None:
    _, key = paystack
    made = (await client.post(CONTRIBUTE, json={**GIFT, "method": "stk"})).json()

    await _webhook(
        client,
        key,
        {"reference": made["reference"], "status": "success", "amount": 100, "currency": "KES"},
    )

    seen = (await client.get(f"/api/pay/{made['reference']}/")).json()
    assert (seen["status"], seen["reason"]) == (
        "failed",
        "Paystack's amount or currency does not match this payment.",
    )


async def test_a_workspace_confirms_or_rejects_the_codes_of_its_contributions(
    client: httpx.AsyncClient, session: AsyncSession, world: World, site: None
) -> None:
    def gift(code: str) -> PaymentIn:
        return PaymentIn(
            method=PayInMethod.MANUAL,
            status=PayInStatus.TO_CONFIRM,
            campaign_id=world.campaign.id,
            amount_kes=500,
            payer_name="Wanjiru",
            payer_phone="+254712345678",
            reference=f"pin-{code}",
            mpesa_code=code,
            provider="manual",
        )

    good, bad = gift("SKL7Q2M9XA"), gift("SKL7Q2M9XB")
    session.add_all([good, bad])
    await session.commit()
    url = f"/api/campaigns/{world.campaign.id}/payments-in/"

    hidden = await client.get(url, headers=world.headers("mobilizer"))
    waiting = await client.get(f"{url}?status=to_confirm", headers=world.headers("manager"))
    confirmed = await client.post(f"{url}{good.id}/confirm/", headers=world.headers("manager"))
    rejected = await client.post(
        f"{url}{bad.id}/reject/",
        json={"reason": "Not on the statement."},
        headers=world.headers("candidate"),
    )

    assert hidden.status_code == 403
    assert {p["mpesa_code"] for p in waiting.json()} == {"SKL7Q2M9XA", "SKL7Q2M9XB"}
    assert (confirmed.json()["status"], rejected.json()["status"]) == ("paid", "rejected")
