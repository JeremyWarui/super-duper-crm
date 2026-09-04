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


# ------------------------------------------------------------- who may send


async def test_inviting_needs_a_token(client: httpx.AsyncClient, session, world: World) -> None:
    event = await _event(session, world)
    response = await client.post(f"/api/events/{event.id}/invite/", json={"message": "Hi"})
    assert response.status_code == 401


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


async def test_a_mobilizer_may_invite_their_own_ward(
    client: httpx.AsyncClient, session, world: World
) -> None:
    event = await _event(session, world)
    response = await client.post(
        f"/api/events/{event.id}/invite/",
        headers=world.headers("mobilizer"),
        json={"message": "Hi"},
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


async def test_a_mobilizer_asking_for_the_whole_campaign_still_gets_their_ward(
    client: httpx.AsyncClient, session, world: World
) -> None:
    event = await _event(session, world)
    await _supporters(
        session,
        world,
        [
            ("Mine", "0712345678", SupportLevel.SUPPORTER, world.ward),
            ("Theirs", "0722000000", SupportLevel.SUPPORTER, world.other_ward),
        ],
    )

    body = (
        await client.post(
            f"/api/events/{event.id}/invite/",
            headers=world.headers("mobilizer"),
            json={"message": "Hi", "whole_campaign": True},
        )
    ).json()

    assert body["supporters_matched"] == 1


# ---------------------------------------------------------------- who it goes to


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


async def test_the_whole_campaign_can_be_invited(
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
            json={"message": "Hi", "whole_campaign": True},
        )
    ).json()

    assert body["supporters_matched"] == 2


async def test_it_can_be_narrowed_to_where_people_stand(
    client: httpx.AsyncClient, session, world: World, gateway: DeliveringProvider
) -> None:
    event = await _event(session, world)
    await _supporters(
        session,
        world,
        [
            ("Supporter", "0712345678", SupportLevel.SUPPORTER, world.ward),
            ("Undecided", "0722000000", SupportLevel.UNDECIDED, world.ward),
            ("Opposed", "0733000000", SupportLevel.OPPOSED, world.ward),
        ],
    )

    body = (
        await client.post(
            f"/api/events/{event.id}/invite/",
            headers=world.headers("manager"),
            json={"message": "Hi", "support_levels": ["supporter", "undecided"]},
        )
    ).json()

    assert body["supporters_matched"] == 2
    assert sorted(gateway.calls[0][0]) == ["+254712345678", "+254722000000"]


async def test_one_person_listed_twice_is_messaged_once(
    client: httpx.AsyncClient, session, world: World, gateway: DeliveringProvider
) -> None:
    event = await _event(session, world)
    await _supporters(
        session,
        world,
        [
            ("Wanjiku", "0712345678", SupportLevel.SUPPORTER, world.ward),
            ("Wanjiku again", "+254712345678", SupportLevel.SUPPORTER, world.ward),
        ],
    )

    body = (
        await client.post(
            f"/api/events/{event.id}/invite/",
            headers=world.headers("manager"),
            json={"message": "Hi"},
        )
    ).json()

    assert body["supporters_matched"] == 2
    assert body["requested"] == 1


async def test_an_unusable_number_is_reported_rather_than_dropped(
    client: httpx.AsyncClient, session, world: World, gateway: DeliveringProvider
) -> None:
    event = await _event(session, world)
    await _supporters(
        session,
        world,
        [
            ("Good", "0712345678", SupportLevel.SUPPORTER, world.ward),
            ("Bad", "not a phone", SupportLevel.SUPPORTER, world.ward),
            ("Blank", "", SupportLevel.SUPPORTER, world.ward),
        ],
    )

    body = (
        await client.post(
            f"/api/events/{event.id}/invite/",
            headers=world.headers("manager"),
            json={"message": "Hi"},
        )
    ).json()

    assert body["supporters_matched"] == 3
    assert body["requested"] == 1
    assert {r["phone"] for r in body["rejected"]} == {"not a phone", ""}


async def test_a_register_with_no_usable_numbers_says_so(
    client: httpx.AsyncClient, session, world: World
) -> None:
    event = await _event(session, world)

    body = (
        await client.post(
            f"/api/events/{event.id}/invite/",
            headers=world.headers("manager"),
            json={"message": "Hi"},
        )
    ).json()

    assert body["requested"] == 0
    assert body["delivered"] is False
    assert "usable phone number" in body["detail"]


# ------------------------------------------------------- what the send does


async def test_nothing_is_sent_until_a_gateway_is_configured(
    client: httpx.AsyncClient, session, world: World
) -> None:
    event = await _event(session, world)
    await _supporters(
        session, world, [("Wanjiku", "0712345678", SupportLevel.SUPPORTER, world.ward)]
    )

    body = (
        await client.post(
            f"/api/events/{event.id}/invite/",
            headers=world.headers("manager"),
            json={"message": "Hi"},
        )
    ).json()

    assert body["provider"] == "console"
    assert body["delivered"] is False
    assert "SMS_PROVIDER=africastalking" in body["detail"]


async def test_a_send_that_did_not_happen_does_not_move_the_reach(
    client: httpx.AsyncClient, session, world: World
) -> None:
    event = await _event(session, world)
    await _supporters(
        session, world, [("Wanjiku", "0712345678", SupportLevel.SUPPORTER, world.ward)]
    )

    body = (
        await client.post(
            f"/api/events/{event.id}/invite/",
            headers=world.headers("manager"),
            json={"message": "Hi"},
        )
    ).json()

    assert body["number_reached"] == 0
    await session.refresh(event)
    assert event.number_reached == 0


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


async def test_the_reply_says_how_many_parts_each_message_costs(
    client: httpx.AsyncClient, session, world: World
) -> None:
    event = await _event(session, world)

    body = (
        await client.post(
            f"/api/events/{event.id}/invite/",
            headers=world.headers("manager"),
            json={"message": "x" * 200},
        )
    ).json()

    assert body["parts"] == 2


async def test_an_empty_message_is_refused(
    client: httpx.AsyncClient, session, world: World
) -> None:
    event = await _event(session, world)
    response = await client.post(
        f"/api/events/{event.id}/invite/",
        headers=world.headers("manager"),
        json={"message": ""},
    )
    assert response.status_code == 400


async def test_an_unknown_event_is_404(client: httpx.AsyncClient, world: World) -> None:
    response = await client.post(
        "/api/events/00000000-0000-0000-0000-000000000009/invite/",
        headers=world.headers("manager"),
        json={"message": "Hi"},
    )
    assert response.status_code == 404
