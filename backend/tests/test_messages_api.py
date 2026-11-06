"""Texts to supporters: drafts and approval, the delivery log, STOP, and the gateway's callbacks,
checked against recorded Africa's Talking replies."""

import json
import secrets
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import CampaignMemberArea, SmsLog, SmsOptOut, Supporter, UserRole
from backend.services.accounts import add_member
from backend.services.sms import AfricasTalkingSMSProvider
from backend.services.texting import FOOTER
from tests.conftest import World
from tests.factories import auth, make_user, sign_in

RECORDED = json.loads((Path(__file__).parent / "fixtures" / "africastalking.json").read_text())


async def _supporter(session, world: World, phone: str, ward, consent: bool = True) -> None:
    session.add(
        Supporter(
            campaign_id=world.campaign.id,
            ward_id=ward.id,
            full_name=f"Supporter {phone[-3:]}",
            phone=phone,
            consent_given=consent,
        )
    )
    await session.commit()


async def _coordinator(session: AsyncSession, client: httpx.AsyncClient, world: World) -> dict:
    """A coordinator whose area is the world's ward."""
    user = await make_user(session, username="coordinator", role=UserRole.COORDINATOR)
    member = await add_member(session, world.campaign.id, user)
    session.add(CampaignMemberArea(campaign_member_id=member.id, ward_id=world.ward.id))
    await session.commit()
    return auth(await sign_in(client, "coordinator"))


async def _log(session: AsyncSession) -> list[tuple]:
    rows = await session.scalars(select(SmsLog).order_by(SmsLog.phone))
    return [(r.phone, r.status, r.provider_id, r.detail) for r in rows]


@pytest.fixture
def secret(monkeypatch: pytest.MonkeyPatch, fresh_settings: None) -> str:
    value = secrets.token_urlsafe(16)
    monkeypatch.setenv("SMS_CALLBACK_SECRET", value)
    return value


async def test_a_coordinator_s_draft_reaches_only_consenting_supporters_in_their_area_once_approved(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await _supporter(session, world, "+254712345678", world.ward)
    await _supporter(session, world, "+254733000000", world.ward, consent=False)
    await _supporter(session, world, "+254722000000", world.ward)
    await _supporter(session, world, "+254744000000", world.other_ward)
    session.add(SmsOptOut(phone="+254722000000", campaign_id=world.campaign.id, source="stop"))
    await session.commit()
    coordinator = await _coordinator(session, client, world)
    draft = {"campaign": str(world.campaign.id), "body": "Town hall on Saturday."}

    sent_at_once = await client.post(
        "/api/messages/", json={**draft, "send": True}, headers=coordinator
    )
    drafted = await client.post("/api/messages/", json=draft, headers=coordinator)
    path = f"/api/messages/{drafted.json()['id']}/send/"
    self_approved = await client.post(path, headers=coordinator)
    before = await _log(session)
    approved = await client.post(path, headers=world.headers("manager"))
    again = await client.post(path, headers=world.headers("manager"))

    assert (sent_at_once.status_code, drafted.status_code, self_approved.status_code) == (
        403,
        201,
        403,
    )
    assert before == []
    assert approved.status_code == 200, approved.text
    assert (approved.json()["status"], approved.json()["recipients"]) == ("sent", 1)
    assert await _log(session) == [("+254712345678", "practice", None, "")]
    assert (await session.scalar(select(SmsLog.body))) == "Town hall on Saturday." + FOOTER
    assert again.status_code == 400


async def test_the_gateway_s_reply_and_its_delivery_reports_land_in_the_log(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    secret: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = AfricasTalkingSMSProvider(
        username="campaign",
        api_key=secrets.token_hex(16),
        transport=httpx.MockTransport(lambda _: httpx.Response(201, json=RECORDED["send"])),
    )
    monkeypatch.setattr("backend.services.texting.get_sms_provider", lambda *a, **k: gateway)
    await _supporter(session, world, "+254712345678", world.ward)
    await _supporter(session, world, "+254722000000", world.other_ward)
    message = {"campaign": str(world.campaign.id), "body": "Polls open at 6.", "send": True}

    sent = await client.post("/api/messages/", json=message, headers=world.headers("candidate"))
    report = f"/api/sms/{secret}/delivery/"
    first = await client.post(report, data=RECORDED["delivery_success"])
    repeat = await client.post(report, data=RECORDED["delivery_success"])
    late = await client.post(report, data=RECORDED["delivery_failed"])

    assert sent.json()["recipients"] == 1
    assert [r.json()["applied"] for r in (first, repeat, late)] == [True, False, False]
    assert await _log(session) == [
        ("+254712345678", "delivered", "ATXid_5b2a8d1c0f3e4a6b9c7d", ""),
        ("+254722000000", "failed", None, "406"),
    ]


async def test_stop_opts_a_number_out_of_the_campaign_that_texted_it_once(
    client: httpx.AsyncClient, session: AsyncSession, world: World, secret: str
) -> None:
    await _supporter(session, world, "+254712345678", world.ward)
    message = {"campaign": str(world.campaign.id), "body": "Rally at 4.", "send": True}
    await client.post("/api/messages/", json=message, headers=world.headers("manager"))

    inbound = f"/api/sms/{secret}/inbound/"
    stop = await client.post(inbound, data=RECORDED["inbound_stop"])
    repeat = await client.post(inbound, data=RECORDED["inbound_stop"])
    gateway = await client.post(f"/api/sms/{secret}/opt-out/", data=RECORDED["gateway_opt_out"])
    preview = await client.post(
        "/api/messages/preview/", json=message, headers=world.headers("manager")
    )
    opted = (await session.execute(select(SmsOptOut.phone, SmsOptOut.campaign_id))).all()

    assert (stop.json()["action"], repeat.json()["action"]) == ("opted_out", "repeat")
    assert gateway.json()["applied"] is True
    assert sorted(opted, key=lambda r: r.phone) == [
        ("+254712345678", world.campaign.id),
        ("+254733000000", None),
    ]
    assert (preview.json()["recipients"], preview.json()["opted_out"]) == (0, 1)


async def test_a_callback_with_the_wrong_secret_is_refused(
    client: httpx.AsyncClient, session: AsyncSession, secret: str
) -> None:
    wrong = await client.post("/api/sms/not-the-secret/inbound/", data=RECORDED["inbound_stop"])

    assert wrong.status_code == 404
    assert (await session.scalar(select(SmsOptOut.id))) is None
