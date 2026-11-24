"""Sozuri: sending in chunks, reading its answer, and its signed delivery reports."""

import hashlib
import hmac
import json
import secrets
import time

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import SmsLog, Supporter
from backend.services.consent import WORDING, ConsentChannel
from backend.services.sms import SozuriSMSProvider
from backend.services.texting import apply_report
from tests.conftest import World

ID_A = "0123456789abcdef0123456789abcdef01234567"
API_KEY = secrets.token_hex(8)
SIGNING = "szs_" + secrets.token_hex(16)


def answer(*recipients: tuple[str, str, str]) -> dict:
    return {
        "messageData": {"messages": sum(s == "sent" for _, s, _ in recipients)},
        "recipients": [
            {"messageId": mid, "to": to, "status": status, "statusCode": "11", "messagePart": 1}
            for to, status, mid in recipients
        ],
    }


def gateway(handler) -> SozuriSMSProvider:  # type: ignore[no-untyped-def]
    return SozuriSMSProvider(
        api_key=API_KEY,
        project="Demo",
        sender_id="CAMPAIGN",
        transport=httpx.MockTransport(handler),
    )


async def test_a_send_is_split_between_taken_refused_and_left_out_numbers() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json=answer(("254712345678", "sent", ID_A), ("254733000000", "unsupported_number", "")),
        )

    result = await gateway(handler).send(
        ["+254712345678", "+254733000000", "+254722000000"], "Polls open at 6. Amina Kariuki"
    )

    body = json.loads(seen[0].content)
    assert seen[0].headers["Authorization"] == f"Bearer {API_KEY}"
    assert seen[0].headers["Idempotency-Key"]
    assert body["to"] == "254712345678,254733000000,254722000000"
    assert (body["project"], body["from"], body["type"]) == ("Demo", "CAMPAIGN", "promotional")
    assert [(r.phone, r.message_id) for r in result.accepted] == [("+254712345678", ID_A)]
    assert [(r.phone, r.status) for r in result.rejected] == [
        ("+254733000000", "unsupported_number"),
        ("+254722000000", "not_sent"),
    ]


async def test_a_refused_request_sends_nothing_and_an_http_error_raises() -> None:
    refused = gateway(
        lambda _: httpx.Response(200, json={"messageData": {"message": "Error. Low balance."}})
    )
    broken = gateway(lambda _: httpx.Response(401, json={"error_code": "AUTHENTICATION_FAILED"}))

    result = await refused.send(["+254712345678"], "Hi")

    assert (result.delivered, result.detail) == (False, "Error. Low balance.")
    assert [r.detail for r in result.rejected] == ["Error. Low balance."]
    with pytest.raises(httpx.HTTPStatusError):
        await broken.send(["+254712345678"], "Hi")


def signed(body: bytes, key: str = SIGNING, stamp: int | None = None) -> dict:
    t = str(stamp or int(time.time()))
    digest = hmac.new(key.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest()
    return {"X-Sozuri-Signature": f"t={t},v1={digest}", "Content-Type": "application/json"}


def report(status: str, message_id: str = ID_A) -> bytes:
    payload = {
        "project": "Demo",
        "messageId": message_id,
        "channel": "sms",
        "status": status,
        "network": "safaricom",
        "type": "bulkDelivery",
        "timestamp": int(time.time()),
    }
    return json.dumps(payload).encode()


async def test_a_signed_delivery_report_lands_once_and_anything_else_changes_nothing(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    monkeypatch: pytest.MonkeyPatch,
    fresh_settings: None,
) -> None:
    secret = secrets.token_urlsafe(16)
    monkeypatch.setenv("SMS_CALLBACK_SECRET", secret)
    monkeypatch.setenv("SOZURI_SIGNING_SECRET", SIGNING)
    sozuri = gateway(
        lambda _: httpx.Response(
            200,
            json=answer(("254712345678", "sent", ID_A), ("254770123456", "sent", "b" * 40)),
        )
    )
    monkeypatch.setattr("backend.services.texting.get_sms_provider", lambda *a, **k: sozuri)
    for phone in ("+254712345678", "+254770123456"):
        session.add(
            Supporter(
                campaign_id=world.campaign.id,
                ward_id=world.ward.id,
                full_name=phone,
                phone=phone,
                consent_given=True,
                consent_wording=WORDING[ConsentChannel.CAMPAIGN_LINK],
                sms_consent=True,
            )
        )
    await session.commit()
    message = {
        "campaign": str(world.campaign.id),
        "body": "Polls open at 6. Amina Kariuki",
        "send": True,
    }
    await client.post("/api/messages/", json=message, headers=world.headers("candidate"))
    url = f"/api/sms/{secret}/sozuri/delivery/"
    good = report("success")

    async def post(body: bytes, headers: dict, path: str = url) -> httpx.Response:
        return await client.post(path, content=body, headers=headers)

    wrong_url = await post(good, signed(good), "/api/sms/nope/sozuri/delivery/")
    unsigned = await post(good, {"Content-Type": "application/json"})
    malformed = await post(good, {"X-Sozuri-Signature": "v1=abc"})
    forged = await post(good, signed(good, key="szs_wrong"))
    stale = await post(good, signed(good, stamp=int(time.time()) - 301))
    tampered = await post(report("success", "c" * 40), signed(good))
    unknown = await post(report("queued"), signed(report("queued")))
    first = await post(good, signed(good))
    repeat = await post(good, signed(good))
    late = await post(report("absent_subscriber"), signed(report("absent_subscriber")))

    assert wrong_url.status_code == 404
    assert [r.status_code for r in (unsigned, malformed, forged, stale, tampered)] == [401] * 5
    assert unknown.json() == {"applied": False}
    assert [r.json()["applied"] for r in (first, repeat, late)] == [True, False, False]
    rows = (await session.execute(select(SmsLog.phone, SmsLog.status, SmsLog.detail))).all()
    assert sorted(tuple(r) for r in rows) == [
        ("+254712345678", "delivered", ""),
        ("+254770123456", "sent", "no_report_expected"),
    ]


@pytest.mark.parametrize(
    ("status", "recorded"),
    [
        ("success", "delivered"),
        ("network_failure", "failed"),
        ("delivery_impossible", "failed"),
        ("absent_subscriber", "failed"),
        ("unknown_error", "failed"),
        ("failed", "failed"),
        ("submitted", "sent"),
    ],
)
async def test_each_sozuri_status_maps_to_one_of_ours(
    session: AsyncSession, status: str, recorded: str
) -> None:
    session.add(
        SmsLog(
            phone="+254712345678",
            body="Hi",
            purpose="test",
            provider="sozuri",
            provider_id=ID_A,
            status="sent",
        )
    )
    await session.commit()

    await apply_report(session, ID_A, status, "" if status == "success" else status, "sozuri")

    row = (await session.execute(select(SmsLog.status, SmsLog.detail))).one()
    failed = recorded == "failed"
    assert tuple(row) == (recorded, status if failed else "")


async def test_the_connection_check_asks_sozuri_and_sends_nothing() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.headers["Authorization"] != f"Bearer {API_KEY}":
            return httpx.Response(401, json={"error_code": "AUTHENTICATION_FAILED"})
        return httpx.Response(200, json={"messageData": {"message": "Success. Project found."}})

    ok = await gateway(handler).check()
    bad = await SozuriSMSProvider(
        api_key=secrets.token_hex(8),
        project="Demo",
        sender_id="X",
        transport=httpx.MockTransport(handler),
    ).check()

    assert ok == (True, "Success. Project found.")
    assert bad[0] is False
    assert {(r.method, r.url.path, r.url.params["project"]) for r in seen} == {
        ("GET", "/api/v1/messaging/authtest", "Demo")
    }


async def test_a_live_test_text_reaches_only_the_campaign_s_own_people_and_is_logged(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sozuri = gateway(lambda _: httpx.Response(200, json=answer(("254711000111", "sent", ID_A))))
    monkeypatch.setattr("backend.services.texting.get_sms_provider", lambda *a, **k: sozuri)
    world.manager.phone = "+254711000111"
    await session.commit()
    body = {"campaign": str(world.campaign.id), "body": "Test from the campaign CRM"}
    manager = world.headers("manager")

    stranger = await client.post(
        "/api/console/sms/test/", json={**body, "phone": "0799000111"}, headers=manager
    )
    own = await client.post(
        "/api/console/sms/test/", json={**body, "phone": "0711 000 111"}, headers=manager
    )
    mobilizer = await client.post(
        "/api/console/sms/test/",
        json={**body, "phone": "0711000111"},
        headers=world.headers("mobilizer"),
    )
    log = await client.get(f"/api/console/sms/test/?campaign={world.campaign.id}", headers=manager)

    assert stranger.status_code == 400
    assert (own.status_code, own.json()["message"]) == (201, "Sent to +254711000111.")
    assert mobilizer.status_code == 403
    assert [(r["phone"], r["status"]) for r in log.json()] == [("+254711000111", "sent")]
