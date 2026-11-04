"""Party payments: the finance officer pays agents and others, practice mode or Paystack."""

import hashlib
import hmac
import json
import secrets
import time
import uuid
from pathlib import Path

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Aspirant, AspirantStatus, PartyRoleName, PaymentStatus, Seat
from backend.services.payouts import PayoutResult, PaystackPayouts
from tests.conftest import World
from tests.factories import auth, make_officer, sign_in

PAYSTACK = json.loads((Path(__file__).parent / "fixtures" / "paystack.json").read_text())
URL = "/api/party/finance/payouts/"


async def _finance(client: httpx.AsyncClient, session: AsyncSession, world: World) -> dict:
    await make_officer(session, world.ward, PartyRoleName.FINANCE_OFFICER, username="pesa")
    return auth(await sign_in(client, "pesa"))


def _agent(**overrides) -> dict:
    return {
        "payee_kind": "polling_agent",
        "name": "Wanjiru Kamau",
        "phone": "0712 345678",
        "purpose": "Polling day",
        "amount_kes": 1500,
        **overrides,
    }


async def test_only_a_finance_officer_schedules_or_releases(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    finance = await _finance(client, session, world)
    await make_officer(session, world.ward, PartyRoleName.MEMBERSHIP_OFFICER, username="usajili")
    other = auth(await sign_in(client, "usajili"))
    made = await client.post(URL, headers=finance, json=_agent(centre=str(world.centre.id)))

    refused_schedule = await client.post(URL, headers=other, json=_agent())
    refused_release = await client.post(f"{URL}{made.json()['id']}/release/", headers=other)
    manager_schedule = await client.post(URL, headers=world.headers("manager"), json=_agent())

    assert made.status_code == 201, made.text
    assert (made.json()["recipient_phone"], made.json()["polling_station"]) == (
        "+254712345678",
        "Zimmerman Primary",
    )
    assert (refused_schedule.status_code, refused_release.status_code) == (403, 403)
    assert manager_schedule.status_code == 403


async def test_a_practice_release_is_paid_under_a_practice_reference(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    finance = await _finance(client, session, world)
    made = (await client.post(URL, headers=finance, json=_agent())).json()

    released = (await client.post(f"{URL}{made['id']}/release/", headers=finance)).json()

    assert (released["status"], released["provider"]) == ("paid", "practice")
    assert released["reference"] == f"PRACTICE-{uuid.UUID(made['id']).hex[:10].upper()}"


@pytest.fixture
def paystack_keys(monkeypatch, fresh_settings) -> dict[str, str]:
    keys = {"secret": secrets.token_hex(20), "webhook": secrets.token_hex(20)}
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", keys["secret"])
    return keys


def _webhook(reference: str, transfer_code: str = "TRF_v0hd9hxmgsq4qwp") -> bytes:
    body = json.loads(json.dumps(PAYSTACK["webhook_success"]))
    body["data"].update(reference=reference, transfer_code=transfer_code)
    return json.dumps(body).encode()


class _Paystack:
    """Paystack as the release sees it: the first send is lost, later ones wait for the webhook."""

    name, moves_money = "paystack", True
    sends: list[str] = []

    async def send(self, *, reference: str, **_: object) -> PayoutResult:
        _Paystack.sends.append(reference)
        if len(_Paystack.sends) == 1:
            raise TimeoutError
        return PayoutResult(PaymentStatus.SENDING, "TRF_v0hd9hxmgsq4qwp")


async def _sending_second_attempt(client, session, world, monkeypatch) -> tuple[dict, dict]:
    """A payment whose first Paystack attempt was settled as not sent, and whose second is out."""
    from backend.api.routers import party_payouts

    finance = await _finance(client, session, world)
    made = (await client.post(URL, headers=finance, json=_agent())).json()
    _Paystack.sends = []
    monkeypatch.setattr(party_payouts, "get_payout_provider", _Paystack)
    await client.post(f"{URL}{made['id']}/release/", headers=finance)
    await client.post(f"{URL}{made['id']}/not-sent/", headers=finance)
    second = (await client.post(f"{URL}{made['id']}/release/", headers=finance)).json()
    assert (second["status"], _Paystack.sends[1]) == ("sending", f"party-{made['id']}-2")
    return finance, made


async def test_a_paystack_webhook_with_a_bad_signature_changes_nothing(
    client: httpx.AsyncClient, session: AsyncSession, world: World, monkeypatch, paystack_keys
) -> None:
    finance, made = await _sending_second_attempt(client, session, world, monkeypatch)
    raw = _webhook(f"party-{made['id']}-2")
    forged = hmac.new(b"not-the-key", raw, hashlib.sha512).hexdigest()

    answer = await client.post(
        "/api/payments/paystack/webhook/", content=raw, headers={"x-paystack-signature": forged}
    )
    after = (await client.get(URL, headers=finance)).json()[0]

    assert answer.status_code == 401
    assert (after["status"], after["paid_at"]) == ("sending", None)


async def test_a_success_webhook_pays_only_the_attempt_it_names(
    client: httpx.AsyncClient, session: AsyncSession, world: World, monkeypatch, paystack_keys
) -> None:
    monkeypatch.setenv("PAYSTACK_WEBHOOK_SECRET", paystack_keys["webhook"])
    finance, made = await _sending_second_attempt(client, session, world, monkeypatch)

    async def deliver(attempt: int) -> dict:
        raw = _webhook(f"party-{made['id']}-{attempt}")
        stamp = str(int(time.time()))
        digest = hmac.new(
            paystack_keys["webhook"].encode(), stamp.encode() + b"." + raw, hashlib.sha512
        ).hexdigest()
        signed = {"paystack-signature": f"t={stamp},v1=whk_test:{digest}"}
        answer = await client.post("/api/payments/paystack/webhook/", content=raw, headers=signed)
        assert answer.status_code == 200, answer.text
        return (await client.get(URL, headers=finance)).json()[0]

    after_first = await deliver(1)
    after_second = await deliver(2)

    assert after_first["status"] == "sending"
    assert (after_second["status"], after_second["reference"]) == ("paid", "TRF_v0hd9hxmgsq4qwp")


async def test_the_spend_per_campaign_adds_up(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    finance = await _finance(client, session, world)
    officer_member = (await make_officer(session, world.ward, username="mgombea")).party_member_id
    aspirant = Aspirant(
        member_id=officer_member,
        seat=Seat.MCA,
        ward_id=world.ward.id,
        status=AspirantStatus.APPROVED,
        campaign_id=world.campaign.id,
    )
    session.add(aspirant)
    await session.commit()
    for amount, aspirant_id, settle in (
        (1_000, aspirant.id, "release"),
        (2_000, aspirant.id, "release"),
        (500, aspirant.id, None),
        (700, aspirant.id, "cancel"),
        (300, None, "release"),
    ):
        made = (
            await client.post(
                URL,
                headers=finance,
                json=_agent(amount_kes=amount, aspirant=str(aspirant_id) if aspirant_id else None),
            )
        ).json()
        if settle:
            await client.post(f"{URL}{made['id']}/{settle}/", headers=finance)

    report = (await client.get(f"{URL}spend/", headers=finance)).json()

    assert [(r["label"], r["paid_kes"], r["owed_kes"], r["payments"]) for r in report["rows"]] == [
        ("Officer mgombea · MCA · Zimmerman", 3_000, 500, 3),
        ("", 300, 0, 1),
    ]
    assert (report["paid_kes"], report["owed_kes"]) == (3_300, 500)


def _recorded(transfer: str, seen: list[httpx.Request]) -> httpx.MockTransport:
    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/transferrecipient":
            return httpx.Response(201, json=PAYSTACK["recipient"])
        code = 400 if transfer == "transfer_refused" else 200
        return httpx.Response(code, json=PAYSTACK[transfer])

    return httpx.MockTransport(answer)


@pytest.mark.parametrize(
    ("transfer", "status", "reference"),
    [
        ("transfer_success", PaymentStatus.PAID, "TRF_1ptvuv321ahaa7q"),
        ("transfer_pending", PaymentStatus.SENDING, "TRF_v0hd9hxmgsq4qwp"),
        ("transfer_refused", PaymentStatus.FAILED, ""),
    ],
)
async def test_paystack_sends_an_mpesa_transfer_for_the_attempt(transfer, status, reference):
    seen: list[httpx.Request] = []
    provider = PaystackPayouts("key", transport=_recorded(transfer, seen))

    result = await provider.send(
        payment_id=uuid.uuid4(),
        reference="party-attempt-reference-1",
        phone="+254712345678",
        name="Wanjiru Kamau",
        amount_kes=1500,
    )

    recipient, sent = (json.loads(r.content) for r in seen)
    assert (recipient["type"], recipient["bank_code"], recipient["account_number"]) == (
        "mobile_money",
        "MPESA",
        "254712345678",
    )
    assert (sent["recipient"], sent["amount"], sent["reference"], sent["currency"]) == (
        "RCP_m7ljkv8leesep7p",
        150_000,
        "party-attempt-reference-1",
        "KES",
    )
    assert (result.status, result.reference) == (status, reference)
