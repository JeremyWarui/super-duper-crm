"""Inviting an event's supporters by SMS."""

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Event, Supporter, SupportLevel
from backend.services.sms import Recipient, SendResult
from tests.conftest import World


async def _event(session: AsyncSession, world: World, *, ward=None) -> Event:
    event = Event(
        campaign_id=world.campaign.id,
        ward_id=(ward or world.ward).id,
        title="Zimmerman town hall",
    )
    session.add(event)
    await session.commit()
    return event


async def _supporters(session: AsyncSession, world: World, rows: list[tuple]) -> None:
    for full_name, phone, level, ward in rows:
        session.add(
            Supporter(
                campaign_id=world.campaign.id,
                ward_id=ward.id if ward else None,
                full_name=full_name,
                phone=phone,
                support_level=level,
                consent_given=True,
            )
        )
    await session.commit()


class DeliveringProvider:
    """Stands in for a gateway that actually took the message."""

    name = "africastalking"

    def __init__(self) -> None:
        self.calls: list[tuple[list[str], str]] = []

    async def send(self, recipients: list[str], message: str) -> SendResult:
        self.calls.append((recipients, message))
        return SendResult(
            provider=self.name,
            delivered=True,
            message=message,
            requested=len(recipients),
            accepted=[Recipient(phone=n, status="Success") for n in recipients],
            detail="Sent",
        )


@pytest.fixture
def gateway(monkeypatch: pytest.MonkeyPatch) -> DeliveringProvider:
    provider = DeliveringProvider()
    monkeypatch.setattr("backend.api.routers.events.get_sms_provider", lambda *a, **k: provider)
    return provider


async def test_a_candidate_may_not_send_invitations(
    client: httpx.AsyncClient, session, world: World
) -> None:
    event = await _event(session, world)
    response = await client.post(
        f"/api/events/{event.id}/invite/",
        headers=world.headers("candidate"),
        json={"message": "Hi"},
    )
    assert response.status_code == 403


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
            json={"message": "Rally Saturday"},
        )
    ).json()

    assert body["supporters_matched"] == 1
    assert gateway.calls == [(["+254712345678"], "Rally Saturday")]


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
            json={"message": "Hi"},
        )
    ).json()

    assert body["delivered"] is True
    assert body["number_reached"] == 2
    await session.refresh(event)
    assert event.number_reached == 2


async def test_a_dry_run_works_out_the_recipients_and_sends_nothing(
    client: httpx.AsyncClient, session, world: World, gateway: DeliveringProvider
) -> None:
    event = await _event(session, world)
    await _supporters(
        session, world, [("Wanjiku", "0712345678", SupportLevel.SUPPORTER, world.ward)]
    )

    body = (
        await client.post(
            f"/api/events/{event.id}/invite/",
            headers=world.headers("manager"),
            json={"message": "Hi", "dry_run": True},
        )
    ).json()

    assert body["dry_run"] is True
    assert body["requested"] == 1
    assert body["accepted"][0]["status"] == "would send"
    assert body["delivered"] is False
    assert gateway.calls == []
    await session.refresh(event)
    assert event.number_reached == 0
