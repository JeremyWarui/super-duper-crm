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
