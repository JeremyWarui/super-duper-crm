"""Payments to mobilizers and agents: only for done assignments, once each, routed to an approver
who never scheduled them, then paid, declined or settled by hand."""

import uuid

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Agent,
    Assignment,
    AssignmentKind,
    AssignmentStatus,
    AuditEvent,
    CampaignMemberArea,
    Event,
    EventStatus,
    Mobilizer,
    UserRole,
    WorkspaceKind,
)
from backend.services.accounts import add_member
from tests.conftest import World
from tests.factories import auth, make_user, sign_in


async def _work(
    session: AsyncSession,
    world: World,
    mobilizer: Mobilizer | None = None,
    *,
    agent: Agent | None = None,
    status: AssignmentStatus = AssignmentStatus.DONE,
    amount: int = 1500,
) -> Assignment:
    """An event in Zimmerman and its assignment to a mobilizer (the world's by default)."""
    if agent is None and mobilizer is None:
        mobilizer = world.mobilizer
    event = Event(
        campaign_id=world.campaign.id,
        ward_id=world.ward.id,
        mobilizer_id=mobilizer.id if mobilizer else None,
        title="Zimmerman town hall",
        status=EventStatus.DONE,
    )
    session.add(event)
    await session.flush()
    work = Assignment(
        campaign_id=world.campaign.id,
        mobilizer_id=mobilizer.id if mobilizer else None,
        agent_id=agent.id if agent else None,
        kind=AssignmentKind.EVENT,
        event_id=event.id,
        ward_id=world.ward.id,
        amount_kes=amount,
        status=status,
    )
    session.add(work)
    await session.commit()
    return work


def _pay(work: Assignment) -> dict:
    return {"assignment": str(work.id)}


async def _schedule(client: httpx.AsyncClient, world: World, work: Assignment, head=None) -> dict:
    made = await client.post(
        "/api/payments/", headers=head or world.headers("manager"), json=_pay(work)
    )
    assert made.status_code == 201, made.text
    return made.json()


async def _coordinator(session: AsyncSession, client: httpx.AsyncClient, world: World) -> dict:
    """A coordinator whose area is Zimmerman, signed in."""
    user = await make_user(session, username="otieno", role=UserRole.COORDINATOR)
    member = await add_member(session, world.campaign.id, user)
    session.add(CampaignMemberArea(campaign_member_id=member.id, ward_id=world.ward.id))
    await session.commit()
    return auth(await sign_in(client, "otieno"))


async def test_a_done_assignment_is_paid_its_amount_once_and_final_once_paid(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    work = await _work(session, world, amount=2500)

    scheduled = await _schedule(client, world, work)
    twice = await client.post("/api/payments/", headers=world.headers("manager"), json=_pay(work))
    paid = await client.post(
        f"/api/payments/{scheduled['id']}/paid/",
        headers=world.headers("candidate"),
        json={"reference": "QX12AB34"},
    )
    again = await client.post(
        f"/api/payments/{scheduled['id']}/decline/",
        headers=world.headers("candidate"),
        json={"reason": "Too late"},
    )

    assert (scheduled["mobilizer"], scheduled["amount_kes"], scheduled["approver_role"]) == (
        str(world.mobilizer.id),
        2500,
        "candidate",
    )
    assert twice.status_code == 400
    assert (paid.json()["status"], paid.json()["reference"]) == ("paid", "QX12AB34")
    assert again.status_code == 400


async def test_no_payment_without_a_done_assignment(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    open_work = await _work(session, world, status=AssignmentStatus.ASSIGNED)

    refused = await client.post(
        "/api/payments/", headers=world.headers("manager"), json=_pay(open_work)
    )
    unknown = await client.post(
        "/api/payments/", headers=world.headers("manager"), json={"assignment": str(uuid.uuid4())}
    )

    assert refused.status_code == 400
    assert refused.json()["detail"] == "Only an assignment marked done can be paid."
    assert unknown.status_code == 400


async def test_the_scheduler_never_approves_their_own_payment(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    work = await _work(session, world)
    made = await _schedule(client, world, work)

    own = await client.post(
        f"/api/payments/{made['id']}/paid/",
        headers=world.headers("manager"),
        json={"reference": "QX1"},
    )

    assert own.status_code == 403
    assert own.json()["detail"] == "You scheduled this payment, so someone else approves it."


async def test_a_coordinator_s_payment_needs_the_manager_and_a_manager_s_the_candidate(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _coordinator(session, client, world)
    by_coordinator = await _schedule(client, world, await _work(session, world), head)
    by_manager = await _schedule(client, world, await _work(session, world))

    candidate_on_coordinators = await client.post(
        f"/api/payments/{by_coordinator['id']}/paid/",
        headers=world.headers("candidate"),
        json={"reference": "A1"},
    )
    manager_on_coordinators = await client.post(
        f"/api/payments/{by_coordinator['id']}/paid/",
        headers=world.headers("manager"),
        json={"reference": "A1"},
    )
    candidate_on_managers = await client.post(
        f"/api/payments/{by_manager['id']}/paid/",
        headers=world.headers("candidate"),
        json={"reference": "A2"},
    )

    assert (by_coordinator["approver_role"], by_manager["approver_role"]) == (
        "manager",
        "candidate",
    )
    assert candidate_on_coordinators.status_code == 403
    assert manager_on_coordinators.json()["status"] == "paid"
    assert candidate_on_managers.json()["status"] == "paid"


@pytest.mark.party_only
async def test_the_party_workspace_manager_cannot_schedule(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    from backend.models import OfficeLevel

    world.campaign.kind = WorkspaceKind.PARTY
    world.campaign.office_level = OfficeLevel.NATIONAL
    world.campaign.constituency_id = None
    world.campaign.seat = None
    await session.commit()
    work = await _work(session, world)

    refused = await client.post("/api/payments/", headers=world.headers("manager"), json=_pay(work))

    assert refused.status_code == 400
    assert "coordinators schedule payments" in refused.json()["detail"]


async def test_a_payee_is_always_a_mobilizer_or_agent_of_the_workspace(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    from backend.models import Campaign, OfficeLevel

    elsewhere = Campaign(
        title="Elsewhere",
        office_level=OfficeLevel.CONSTITUENCY,
        constituency_id=world.constituency.id,
    )
    session.add(elsewhere)
    await session.flush()
    stranger = Mobilizer(campaign_id=elsewhere.id, ward_id=world.ward.id, full_name="Stranger")
    session.add(stranger)
    await session.commit()
    event = Event(campaign_id=world.campaign.id, ward_id=world.ward.id, title="Rally")
    session.add(event)
    await session.commit()

    refused = await client.post(
        "/api/assignments/",
        headers=world.headers("manager"),
        json={
            "campaign": str(world.campaign.id),
            "mobilizer": str(stranger.id),
            "kind": "event",
            "event": str(event.id),
            "amount_kes": 1000,
        },
    )

    assert refused.status_code == 400
    assert refused.json()["detail"] == "No such mobilizer on this campaign."


async def test_an_agent_is_paid_and_sees_only_their_own_payment(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    agent_user = await make_user(session, username="wekesa", role=UserRole.AGENT)
    await add_member(session, world.campaign.id, agent_user)
    agent = Agent(
        campaign_id=world.campaign.id,
        user_id=agent_user.id,
        ward_id=world.ward.id,
        registration_centre_id=world.centre.id,
    )
    session.add(agent)
    await session.commit()
    await _schedule(client, world, await _work(session, world, agent=agent))
    await _schedule(client, world, await _work(session, world))

    own = (await client.get("/api/payments/", headers=auth(await sign_in(client, "wekesa")))).json()

    assert [(p["agent"], p["mobilizer"]) for p in own] == [(str(agent.id), None)]


async def test_every_schedule_approval_and_decline_is_audited(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    paid = await _schedule(client, world, await _work(session, world))
    declined = await _schedule(client, world, await _work(session, world))
    await client.post(
        f"/api/payments/{paid['id']}/paid/",
        headers=world.headers("candidate"),
        json={"reference": "QX9"},
    )
    await client.post(
        f"/api/payments/{declined['id']}/decline/",
        headers=world.headers("candidate"),
        json={"reason": "Not done properly"},
    )

    actions = (
        await session.scalars(select(AuditEvent.action).where(AuditEvent.subject_type == "payment"))
    ).all()

    assert sorted(actions) == [
        "payment.decline",
        "payment.mark_paid",
        "payment.schedule",
        "payment.schedule",
    ]


async def test_a_blank_reference_does_not_mark_a_payment_paid(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    made = await _schedule(client, world, await _work(session, world))

    blank = await client.post(
        f"/api/payments/{made['id']}/paid/",
        headers=world.headers("candidate"),
        json={"reference": "   "},
    )

    assert blank.status_code == 400


async def test_a_release_in_practice_mode_pays_once_under_a_practice_reference(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    world.mobilizer.phone = "0712 345678"
    made = await _schedule(client, world, await _work(session, world))
    head = world.headers("candidate")

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
    made = await _schedule(client, world, await _work(session, world))

    released = await client.post(
        f"/api/payments/{made['id']}/release/", headers=world.headers("candidate")
    )
    listed = (await client.get("/api/payments/", headers=world.headers("manager"))).json()

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

    world.mobilizer.phone = "0712 345678"
    made = await _schedule(client, world, await _work(session, world))
    monkeypatch.setattr(payments, "get_payout_provider", _Unreachable)
    head = world.headers("candidate")

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

    world.mobilizer.phone = "0712 345678"
    made = await _schedule(client, world, await _work(session, world))
    monkeypatch.setattr(payments, "get_payout_provider", _Confirms)
    head = world.headers("candidate")

    sent = (await client.post(f"/api/payments/{made['id']}/release/", headers=head)).json()
    not_sent = await client.post(f"/api/payments/{made['id']}/not-sent/", headers=head)
    paid = await client.post(
        f"/api/payments/{made['id']}/paid/", headers=head, json={"reference": "X1"}
    )

    assert (sent["status"], sent["stuck"]) == ("sending", False)
    assert (not_sent.status_code, paid.status_code) == (400, 400)
