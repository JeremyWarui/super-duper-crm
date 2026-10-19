"""Payments to mobilizers: scheduled per event, then paid or cancelled, and who sees them."""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Event, EventStatus, Mobilizer
from tests.conftest import World


async def _event(session: AsyncSession, world: World, mobilizer: Mobilizer) -> Event:
    event = Event(
        campaign_id=world.campaign.id,
        ward_id=world.ward.id,
        mobilizer_id=mobilizer.id,
        title="Zimmerman town hall",
        status=EventStatus.DONE,
    )
    session.add(event)
    await session.commit()
    return event


def _payment(world: World, event: Event, **overrides) -> dict:
    return {
        "campaign": str(world.campaign.id),
        "event": str(event.id),
        "amount_kes": 1500,
        **overrides,
    }


async def test_a_payment_goes_to_the_event_s_mobilizer_and_is_final_once_paid(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = world.headers("manager")
    event = await _event(session, world, world.mobilizer)

    scheduled = (
        await client.post("/api/payments/", headers=head, json=_payment(world, event))
    ).json()
    paid = await client.post(
        f"/api/payments/{scheduled['id']}/paid/", headers=head, json={"reference": "QX12AB34"}
    )
    again = await client.post(f"/api/payments/{scheduled['id']}/cancel/", headers=head)

    assert (scheduled["mobilizer"], scheduled["recipient_name"], scheduled["status"]) == (
        str(world.mobilizer.id),
        "Juma Otieno",
        "scheduled",
    )
    assert (paid.json()["status"], paid.json()["reference"]) == ("paid", "QX12AB34")
    assert again.status_code == 400


async def test_the_candidate_reads_and_a_mobilizer_sees_only_their_own(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    other = Mobilizer(
        campaign_id=world.campaign.id, ward_id=world.other_ward.id, full_name="Akinyi"
    )
    session.add(other)
    await session.commit()
    for mobilizer in (world.mobilizer, other):
        event = await _event(session, world, mobilizer)
        made = await client.post(
            "/api/payments/", headers=world.headers("manager"), json=_payment(world, event)
        )
        assert made.status_code == 201, made.text

    candidate_reads = await client.get("/api/payments/", headers=world.headers("candidate"))
    candidate_writes = await client.post(
        "/api/payments/", headers=world.headers("candidate"), json=_payment(world, event)
    )
    own = (await client.get("/api/payments/", headers=world.headers("mobilizer"))).json()

    assert len(candidate_reads.json()) == 2
    assert candidate_writes.status_code == 403
    assert [p["recipient_name"] for p in own] == ["Juma Otieno"]


async def test_an_event_is_not_paid_twice_to_the_same_mobilizer(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = world.headers("manager")
    event = await _event(session, world, world.mobilizer)

    first = await client.post("/api/payments/", headers=head, json=_payment(world, event))
    second = await client.post("/api/payments/", headers=head, json=_payment(world, event))

    assert (first.status_code, second.status_code) == (201, 400)


async def test_a_blank_reference_does_not_mark_a_payment_paid(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = world.headers("manager")
    event = await _event(session, world, world.mobilizer)
    made = (await client.post("/api/payments/", headers=head, json=_payment(world, event))).json()

    blank = await client.post(
        f"/api/payments/{made['id']}/paid/", headers=head, json={"reference": "   "}
    )

    assert blank.status_code == 400


async def test_a_release_in_practice_mode_pays_once_under_a_practice_reference(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = world.headers("manager")
    world.mobilizer.phone = "0712 345678"
    event = await _event(session, world, world.mobilizer)
    made = (await client.post("/api/payments/", headers=head, json=_payment(world, event))).json()

    released = await client.post(f"/api/payments/{made['id']}/release/", headers=head)
    again = await client.post(f"/api/payments/{made['id']}/release/", headers=head)

    body = released.json()
    assert (body["status"], body["provider"], body["recipient_phone"]) == (
        "paid",
        "practice",
        "+254712345678",
    )
    assert body["reference"].startswith("PRACTICE-")
    assert again.status_code == 400


async def test_a_release_without_a_usable_phone_sends_nothing(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = world.headers("manager")
    event = await _event(session, world, world.mobilizer)
    made = (await client.post("/api/payments/", headers=head, json=_payment(world, event))).json()

    released = await client.post(f"/api/payments/{made['id']}/release/", headers=head)
    listed = (await client.get("/api/payments/", headers=head)).json()

    assert released.status_code == 400
    assert [p["status"] for p in listed] == ["scheduled"]


class _Unreachable:
    name, moves_money = "broken", True

    async def send(self, **_: object) -> None:
        raise TimeoutError


async def test_an_unknown_outcome_waits_for_a_person_instead_of_paying_twice(
    client: httpx.AsyncClient, session: AsyncSession, world: World, monkeypatch
) -> None:
    from backend.api.routers import payments

    head = world.headers("manager")
    world.mobilizer.phone = "0712 345678"
    event = await _event(session, world, world.mobilizer)
    made = (await client.post("/api/payments/", headers=head, json=_payment(world, event))).json()
    monkeypatch.setattr(payments, "get_payout_provider", _Unreachable)

    stuck = (await client.post(f"/api/payments/{made['id']}/release/", headers=head)).json()
    retried = await client.post(f"/api/payments/{made['id']}/release/", headers=head)
    settled = await client.post(f"/api/payments/{made['id']}/not-sent/", headers=head)

    assert (stuck["status"], stuck["failure_reason"].startswith("Outcome unknown")) == (
        "sending",
        True,
    )
    assert retried.status_code == 400
    assert settled.json()["status"] == "failed"


class _Confirms:
    """A provider that accepts the transfer and confirms it later."""

    name, moves_money = "later", True

    async def send(self, **_: object):
        from backend.models import PaymentStatus
        from backend.services.payouts import PayoutResult

        return PayoutResult(PaymentStatus.SENDING, "TRF_1")


async def test_a_send_still_in_flight_cannot_be_settled_by_hand(
    client: httpx.AsyncClient, session: AsyncSession, world: World, monkeypatch
) -> None:
    from backend.api.routers import payments

    head = world.headers("manager")
    world.mobilizer.phone = "0712 345678"
    event = await _event(session, world, world.mobilizer)
    made = (await client.post("/api/payments/", headers=head, json=_payment(world, event))).json()
    monkeypatch.setattr(payments, "get_payout_provider", _Confirms)

    sent = (await client.post(f"/api/payments/{made['id']}/release/", headers=head)).json()
    not_sent = await client.post(f"/api/payments/{made['id']}/not-sent/", headers=head)
    paid = await client.post(
        f"/api/payments/{made['id']}/paid/", headers=head, json={"reference": "X1"}
    )

    assert (sent["status"], sent["stuck"]) == ("sending", False)
    assert (not_sent.status_code, paid.status_code) == (400, 400)
