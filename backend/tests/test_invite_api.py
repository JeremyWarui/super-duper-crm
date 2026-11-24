"""Inviting an event's supporters by SMS."""

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Event, SmsLog, SmsOptOut, Supporter, SupportLevel
from backend.services.consent import WORDING, ConsentChannel
from backend.services.sms import Recipient, SendResult
from backend.services.texting import FOOTER
from tests.conftest import World

NAME = "Amina Kariuki"


async def _event(session: AsyncSession, world: World, *, ward=None) -> Event:
    event = Event(
        campaign_id=world.campaign.id,
        ward_id=(ward or world.ward).id,
        title="Zimmerman town hall",
    )
    session.add(event)
    await session.commit()
    return event


async def _supporters(
    session: AsyncSession, world: World, rows: list[tuple], consent: bool = True
) -> None:
    for full_name, phone, level, ward in rows:
        session.add(
            Supporter(
                campaign_id=world.campaign.id,
                ward_id=ward.id if ward else None,
                full_name=full_name,
                phone=phone,
                support_level=level,
                consent_given=consent,
                consent_wording=WORDING[ConsentChannel.CAMPAIGN_LINK] if consent else None,
                sms_consent=consent,
            )
        )
    await session.commit()


class DeliveringProvider:
    """Stands in for a gateway that actually took the message."""

    name = "africastalking"

    def __init__(self) -> None:
        self.calls: list[tuple[list[str], str]] = []

    async def send(
        self, recipients: list[str], message: str, idempotency_key: str | None = None
    ) -> SendResult:
        self.calls.append((recipients, message))
        return SendResult(
            provider=self.name,
            delivered=True,
            message=message,
            requested=len(recipients),
            accepted=[
                Recipient(phone=n, status="Success", message_id=f"ATXid_{n}") for n in recipients
            ],
            detail="Sent",
        )


@pytest.fixture
def gateway(monkeypatch: pytest.MonkeyPatch) -> DeliveringProvider:
    provider = DeliveringProvider()
    monkeypatch.setattr("backend.services.texting.get_sms_provider", lambda *a, **k: provider)
    return provider


async def test_a_candidate_may_send_invitations(
    client: httpx.AsyncClient, session, world: World
) -> None:
    event = await _event(session, world)
    response = await client.post(
        f"/api/events/{event.id}/invite/",
        headers=world.headers("candidate"),
        json={"message": f"Hi. {NAME}", "dry_run": True},
    )
    assert response.status_code == 200


async def test_a_mobilizer_cannot_invite_another_ward_s_event(
    client: httpx.AsyncClient, session, world: World
) -> None:
    event = await _event(session, world, ward=world.other_ward)
    response = await client.post(
        f"/api/events/{event.id}/invite/",
        headers=world.headers("mobilizer"),
        json={"message": "Hi"},
    )
    assert response.status_code == 403


async def test_it_goes_to_the_supporters_in_the_event_s_ward(
    client: httpx.AsyncClient, session, world: World, gateway: DeliveringProvider
) -> None:
    event = await _event(session, world)
    await _supporters(
        session,
        world,
        [
            ("Here", "0712345678", SupportLevel.SUPPORTER, world.ward),
            ("Elsewhere", "0722000000", SupportLevel.SUPPORTER, world.other_ward),
        ],
    )

    body = (
        await client.post(
            f"/api/events/{event.id}/invite/",
            headers=world.headers("manager"),
            json={"message": f"Rally Saturday. {NAME}"},
        )
    ).json()

    assert body["supporters_matched"] == 1
    assert gateway.calls == [(["+254712345678"], f"Rally Saturday. {NAME}" + FOOTER)]


async def test_a_delivered_invitation_sets_the_number_reached(
    client: httpx.AsyncClient, session, world: World, gateway: DeliveringProvider
) -> None:
    event = await _event(session, world)
    await _supporters(
        session,
        world,
        [
            ("One", "0712345678", SupportLevel.SUPPORTER, world.ward),
            ("Two", "0722000000", SupportLevel.SUPPORTER, world.ward),
        ],
    )

    body = (
        await client.post(
            f"/api/events/{event.id}/invite/",
            headers=world.headers("manager"),
            json={"message": f"Hi. {NAME}"},
        )
    ).json()

    assert body["delivered"] is True
    assert body["number_reached"] == 2
    await session.refresh(event)
    assert event.number_reached == 2


@pytest.mark.parametrize("role", ["manager", "mobilizer"])
async def test_a_dry_run_counts_the_recipients_sends_nothing_and_shows_no_number(
    client: httpx.AsyncClient, session, world: World, gateway: DeliveringProvider, role: str
) -> None:
    event = await _event(session, world)
    await _supporters(
        session, world, [("Wanjiku", "0712345678", SupportLevel.SUPPORTER, world.ward)]
    )

    body = (
        await client.post(
            f"/api/events/{event.id}/invite/",
            headers=world.headers(role),
            json={"message": f"Hi. {NAME}", "dry_run": True},
        )
    ).json()

    assert body["dry_run"] is True
    assert body["requested"] == 1
    assert body["accepted"] == []
    assert "712345678" not in str(body)
    assert body["estimated_cost_cents"] == body["parts"] * 80
    assert body["delivered"] is False
    assert gateway.calls == []
    await session.refresh(event)
    assert event.number_reached == 0


async def test_it_skips_opted_out_and_unconsented_numbers_and_logs_who_was_texted(
    client: httpx.AsyncClient, session, world: World, gateway: DeliveringProvider
) -> None:
    event = await _event(session, world)
    await _supporters(
        session,
        world,
        [
            ("Texted", "0712345678", SupportLevel.SUPPORTER, world.ward),
            ("Said stop", "0722000000", SupportLevel.SUPPORTER, world.ward),
        ],
    )
    await _supporters(
        session, world, [("No consent", "0733000000", SupportLevel.SUPPORTER, world.ward)], False
    )
    session.add(SmsOptOut(phone="+254722000000", campaign_id=world.campaign.id, source="stop"))
    await session.commit()

    body = (
        await client.post(
            f"/api/events/{event.id}/invite/",
            headers=world.headers("manager"),
            json={"message": f"Rally Saturday. {NAME}"},
        )
    ).json()
    logged = (await session.scalars(select(SmsLog).where(SmsLog.event_id == event.id))).all()

    assert body["opted_out"] == 1
    assert [numbers for numbers, _ in gateway.calls] == [["+254712345678"]]
    assert [(r.phone, r.status, r.purpose) for r in logged] == [("+254712345678", "sent", "invite")]


async def test_an_invitation_goes_through_the_queue_s_checks(
    client: httpx.AsyncClient, session, world: World, gateway: DeliveringProvider
) -> None:
    event = await _event(session, world)
    await _supporters(session, world, [("One", "0712345678", SupportLevel.SUPPORTER, world.ward)])
    url = f"/api/events/{event.id}/invite/"

    unnamed = await client.post(url, headers=world.headers("manager"), json={"message": "Hi"})
    named = await client.post(
        url, headers=world.headers("manager"), json={"message": f"Hi. {NAME}"}
    )

    assert unnamed.status_code == 400 and NAME in unnamed.json()["detail"]
    assert (named.json()["run_status"], named.json()["queued"]) == ("completed", 1)
