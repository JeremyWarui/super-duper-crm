"""The finance officer's ledger: payments, extensions, voids, holds, and who may touch them."""

import asyncio
import json
import uuid
from datetime import date, timedelta

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from backend.models import (
    Aspirant,
    AspirantStatus,
    AuditEvent,
    CampaignSubscription,
    PartyRoleName,
    PartySettings,
    ReceiptMethod,
    Seat,
    SubscriptionHold,
    User,
)
from backend.schemas.billing import PaymentCreate
from backend.services import billing
from tests.conftest import POSTGRES, World
from tests.factories import TEST_TODAY, auth, make_officer, make_rival_campaign, sign_in

DAYS = 30


async def _finance(client: httpx.AsyncClient, session: AsyncSession, world: World) -> dict:
    await make_officer(session, world.ward, PartyRoleName.FINANCE_OFFICER, username="pesa")
    return auth(await sign_in(client, "pesa"))


async def _on_plan(client: httpx.AsyncClient, headers: dict, world: World) -> str:
    """The world campaign's subscription id, on a 30-day plan."""
    plan = await client.post(
        "/api/party/finance/plans/",
        headers=headers,
        json={"name": "Monthly", "price_kes": 5_000, "duration_days": DAYS},
    )
    sub_id = str(world.campaign.subscription.id)
    chosen = await client.put(
        f"/api/party/finance/subscriptions/{sub_id}/plan/",
        headers=headers,
        json={"plan": plan.json()["id"]},
    )
    assert chosen.status_code == 200, chosen.text
    return sub_id


async def _paid_until(session: AsyncSession, world: World, day) -> None:
    await session.execute(
        update(CampaignSubscription)
        .where(CampaignSubscription.campaign_id == world.campaign.id)
        .values(paid_until=day)
    )
    await session.commit()


def _payment(reference: str, received_on=TEST_TODAY) -> dict:
    return {
        "amount_kes": 5_000,
        "method": "mpesa",
        "reference": reference,
        "received_on": received_on.isoformat(),
    }


async def _pay(client, headers, sub_id, reference, received_on=TEST_TODAY) -> httpx.Response:
    return await client.post(
        f"/api/party/finance/subscriptions/{sub_id}/payments/",
        headers=headers,
        json=_payment(reference, received_on),
    )


async def test_a_payment_after_a_lapse_runs_from_the_day_it_arrived(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    headers = await _finance(client, session, world)
    sub_id = await _on_plan(client, headers, world)
    await _paid_until(session, world, TEST_TODAY - timedelta(days=40))
    received = TEST_TODAY - timedelta(days=2)

    paid = (await _pay(client, headers, sub_id, "sk1 lapsed", received)).json()

    assert paid["paid_until"] == (received + timedelta(days=DAYS - 1)).isoformat()
    assert paid["state"] == "active"
    assert paid["entries"][0]["reference"] == "SK1LAPSED"


async def test_an_early_payment_adds_its_days_after_the_paid_period(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    headers = await _finance(client, session, world)
    sub_id = await _on_plan(client, headers, world)
    ends = TEST_TODAY + timedelta(days=10)
    await _paid_until(session, world, ends)

    paid = (await _pay(client, headers, sub_id, "EARLY1")).json()

    assert paid["paid_until"] == (ends + timedelta(days=DAYS)).isoformat()


async def test_only_the_latest_entry_is_voided_and_the_paid_date_goes_back(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    headers = await _finance(client, session, world)
    sub_id = await _on_plan(client, headers, world)
    await _paid_until(session, world, None)
    first = (await _pay(client, headers, sub_id, "FIRST")).json()
    second = (await _pay(client, headers, sub_id, "SECOND")).json()
    older, newer = second["entries"][1]["id"], second["entries"][0]["id"]
    url = f"/api/party/finance/subscriptions/{sub_id}/entries"
    reason = {"reason": "Recorded against the wrong campaign."}

    refused = await client.post(f"{url}/{older}/void/", headers=headers, json=reason)
    voided = (await client.post(f"{url}/{newer}/void/", headers=headers, json=reason)).json()
    reused = await _pay(client, headers, sub_id, "SECOND")

    assert refused.status_code == 400
    assert voided["paid_until"] == first["paid_until"]
    assert [e["can_void"] for e in voided["entries"]] == [False, True]
    assert reused.status_code == 201


async def test_a_hold_locks_a_paid_campaign_and_lifting_it_restores_access(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    headers = await _finance(client, session, world)
    sub_id = str(world.campaign.subscription.id)
    url = f"/api/party/finance/subscriptions/{sub_id}/hold/"
    manager = world.headers("manager")

    without_reason = await client.put(url, headers=headers, json={"hold": "suspended"})
    held = await client.put(url, headers=headers, json={"hold": "suspended", "reason": "Unpaid"})
    locked = await client.get("/api/campaigns/", headers=manager)
    lifted = await client.put(url, headers=headers, json={"hold": "none"})
    reopened = await client.get("/api/campaigns/", headers=manager)

    assert without_reason.status_code == 400
    assert held.json()["state"] == "locked"
    assert (locked.status_code, locked.json()["code"]) == (403, "campaign_locked")
    assert (lifted.json()["state"], lifted.json()["hold_reason"]) == ("active", None)
    assert reopened.status_code == 200


async def test_finance_is_closed_to_other_party_offices(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await make_officer(session, world.ward, PartyRoleName.NOMINATIONS_OFFICER, username="teuzi")
    headers = auth(await sign_in(client, "teuzi"))

    answers = [
        (await client.get("/api/party/finance/subscriptions/", headers=headers)).status_code,
        (await client.get("/api/party/finance/plans/", headers=headers)).status_code,
        (
            await client.get(
                "/api/party/finance/subscriptions/", headers=world.headers("candidate")
            )
        ).status_code,
    ]

    assert answers == [403, 403, 403]


OWN_WRITES = [
    ("PUT", "plan/", None),
    ("POST", "payments/", _payment("OWN1")),
    ("POST", "extensions/", {"days": 5, "note": "Goodwill"}),
    ("PUT", "hold/", {"hold": "suspended", "reason": "Unpaid"}),
    ("POST", "entries/{entry}/void/", {"reason": "Entered twice"}),
]


@pytest.mark.parametrize(("method", "path", "body"), OWN_WRITES)
async def test_a_finance_officer_cannot_touch_their_own_campaigns_money(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    method: str,
    path: str,
    body: dict | None,
) -> None:
    headers = await _finance(client, session, world)
    sub_id = await _on_plan(client, headers, world)
    await _pay(client, headers, sub_id, "BEFORE1")
    officer = await session.scalar(select(User).where(User.username == "pesa"))
    session.add(
        Aspirant(
            member_id=officer.party_member_id,
            seat=Seat.MP,
            constituency_id=world.constituency.id,
            status=AspirantStatus.APPROVED,
            campaign_id=world.campaign.id,
        )
    )
    await session.commit()

    plan_id = (await client.get("/api/party/finance/plans/", headers=headers)).json()[0]["id"]
    url = f"/api/party/finance/subscriptions/{sub_id}/"
    entry = (await client.get(url, headers=headers)).json()["entries"][0]["id"]

    written = await client.request(
        method, url + path.format(entry=entry), headers=headers, json=body or {"plan": plan_id}
    )
    seen = await client.get(url, headers=headers)

    assert written.status_code == 403
    assert seen.status_code == 200


async def test_deleting_a_campaign_keeps_its_ledger_under_its_name(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    headers = await _finance(client, session, world)
    sub_id = await _on_plan(client, headers, world)
    await _pay(client, headers, sub_id, "KEPT1")

    deleted = await client.delete(
        f"/api/admin/campaigns/{world.campaign.id}/", headers=admin_headers
    )
    kept = (await client.get(f"/api/party/finance/subscriptions/{sub_id}/", headers=headers)).json()

    assert deleted.status_code == 204
    assert (kept["campaign_id"], kept["title"]) == (None, "Jane for Roysambu")
    assert [e["reference"] for e in kept["entries"]] == ["KEPT1"]


@pytest.mark.skipif(not POSTGRES, reason="row locks need TEST_POSTGRES=1")
async def test_two_payments_at_once_both_land_one_after_the_other(
    engine: AsyncEngine,
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = await _finance(client, session, world)
    sub_id = await _on_plan(client, headers, world)
    await _paid_until(session, world, None)
    officer = await session.scalar(select(User).where(User.username == "pesa"))
    # Each payment, once it has read the subscription, waits briefly for the other to read it
    # too: without the row lock both then read the same paid date; with it the second is still
    # blocked in the database and the first goes on alone.
    read_it = asyncio.Barrier(2)
    reading = billing._locked

    async def read_then_meet(*args, **kwargs):
        sub = await reading(*args, **kwargs)
        try:
            async with asyncio.timeout(0.5):
                await read_it.wait()
        except TimeoutError:
            pass
        return sub

    monkeypatch.setattr(billing, "_locked", read_then_meet)

    async def pay(reference: str) -> None:
        async with AsyncSession(engine, expire_on_commit=False) as own:
            await billing.record_payment(
                own,
                uuid.UUID(sub_id),
                PaymentCreate(
                    amount_kes=5_000,
                    method=ReceiptMethod.MPESA,
                    reference=reference,
                    received_on=TEST_TODAY,
                ),
                actor=officer,
                on=TEST_TODAY,
            )

    await asyncio.gather(pay("RACE1"), pay("RACE2"))
    detail = await billing.subscription(session, uuid.UUID(sub_id), TEST_TODAY)

    assert detail.paid_until == TEST_TODAY + timedelta(days=2 * DAYS - 1)
    newer, older = detail.entries
    assert (older.paid_until_before, newer.paid_until_before) == (None, older.paid_until_after)


async def test_an_extension_adds_free_days_from_today_and_needs_a_reason(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    headers = await _finance(client, session, world)
    sub_id = await _on_plan(client, headers, world)
    await _paid_until(session, world, None)
    url = f"/api/party/finance/subscriptions/{sub_id}/extensions/"

    unexplained = await client.post(url, headers=headers, json={"days": 10, "note": " "})
    extended = (await client.post(url, headers=headers, json={"days": 10, "note": "Trial"})).json()

    assert unexplained.status_code == 400
    assert extended["paid_until"] == (TEST_TODAY + timedelta(days=9)).isoformat()
    assert (extended["entries"][0]["kind"], extended["entries"][0]["amount_kes"]) == (
        "extension",
        None,
    )


@pytest.mark.parametrize(
    "received_on", [TEST_TODAY + timedelta(days=1), TEST_TODAY - timedelta(days=366)]
)
async def test_a_payment_dated_after_today_or_over_a_year_ago_is_refused(
    client: httpx.AsyncClient, session: AsyncSession, world: World, received_on
) -> None:
    headers = await _finance(client, session, world)
    sub_id = await _on_plan(client, headers, world)

    refused = await _pay(client, headers, sub_id, "DATED1", received_on)

    assert refused.status_code == 400


@pytest.mark.parametrize("spelling", ["abc123", "ABC 123", "ABC 123", "ＡＢＣ１２３"])
async def test_a_reference_cannot_be_recorded_twice_under_another_spelling(
    client: httpx.AsyncClient, session: AsyncSession, world: World, spelling: str
) -> None:
    headers = await _finance(client, session, world)
    sub_id = await _on_plan(client, headers, world)
    await _pay(client, headers, sub_id, "ABC123")

    again = await _pay(client, headers, sub_id, spelling)

    assert again.status_code == 400


@pytest.mark.parametrize("reference", ["ß" * 40, "ﬃ" * 20, "SK1;DROP"])
async def test_a_reference_that_is_not_letters_and_digits_is_refused(
    client: httpx.AsyncClient, session: AsyncSession, world: World, reference: str
) -> None:
    headers = await _finance(client, session, world)
    sub_id = await _on_plan(client, headers, world)

    refused = await _pay(client, headers, sub_id, reference)

    assert refused.status_code == 400


async def test_an_inactive_plan_cannot_be_chosen(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    headers = await _finance(client, session, world)
    plan = await client.post(
        "/api/party/finance/plans/",
        headers=headers,
        json={"name": "Retired", "price_kes": 1_000, "duration_days": 7, "active": False},
    )

    chosen = await client.put(
        f"/api/party/finance/subscriptions/{world.campaign.subscription.id}/plan/",
        headers=headers,
        json={"plan": plan.json()["id"]},
    )

    assert chosen.status_code == 400


async def test_the_audit_trail_holds_no_reference_or_note(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    headers = await _finance(client, session, world)
    sub_id = await _on_plan(client, headers, world)
    base = f"/api/party/finance/subscriptions/{sub_id}"
    payment = _payment("AUDIT77") | {"note": "Paid by Kamau"}
    await client.post(f"{base}/payments/", headers=headers, json=payment)
    extension = {"days": 3, "note": "Rainy week"}
    latest = (await client.post(f"{base}/extensions/", headers=headers, json=extension)).json()
    voided = await client.post(
        f"{base}/entries/{latest['entries'][0]['id']}/void/",
        headers=headers,
        json={"reason": "Wrong amount"},
    )
    await client.put(
        f"{base}/hold/", headers=headers, json={"hold": "suspended", "reason": "Fraud"}
    )

    events = (
        await session.execute(
            select(AuditEvent.action, AuditEvent.detail).where(AuditEvent.action.like("finance.%"))
        )
    ).all()
    details = json.dumps([detail for _, detail in events])

    assert voided.status_code == 200
    assert {action for action, _ in events} >= {
        "finance.subscription.payment",
        "finance.subscription.extension",
        "finance.subscription.void",
        "finance.subscription.hold",
    }
    for secret in ("AUDIT77", "Kamau", "Rainy", "Wrong amount", "Fraud"):
        assert secret not in details
    assert not any({"reference", "note", "reason"} & set(detail) for _, detail in events)


async def test_revenue_counts_live_payments_only(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    headers = await _finance(client, session, world)
    sub_id = await _on_plan(client, headers, world)
    await _paid_until(session, world, None)
    base = f"/api/party/finance/subscriptions/{sub_id}"
    await _pay(client, headers, sub_id, "KEPT", TEST_TODAY - timedelta(days=40))
    wrong = (await _pay(client, headers, sub_id, "WRONG")).json()["entries"][0]["id"]
    await client.post(f"{base}/entries/{wrong}/void/", headers=headers, json={"reason": "Typo"})
    await client.post(f"{base}/extensions/", headers=headers, json={"days": 5, "note": "Free"})

    report = (await client.get("/api/party/finance/reports/revenue/", headers=headers)).json()

    assert (report["start"], report["end"]) == ("2026-01-01", "2026-12-31")
    assert (report["total_kes"], report["count"]) == (5_000, 1)
    assert report["by_month"] == [{"month": "2026-09", "total_kes": 5_000, "count": 1}]
    assert [line["plan"]["name"] for line in report["by_plan"]] == ["Monthly"]


async def _rival(session: AsyncSession, world: World, title: str, paid_until, **fields):
    campaign = await make_rival_campaign(session, world.ward, title=title, owner=title.lower())
    await session.execute(
        update(CampaignSubscription)
        .where(CampaignSubscription.campaign_id == campaign.id)
        .values(paid_until=paid_until, **fields)
    )
    await session.commit()
    return campaign


async def test_the_expiring_list_holds_lapsing_campaigns_soonest_first(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    session.add(PartySettings(id=1, name="Party", grace_days=3, read_only_days=4))
    headers = await _finance(client, session, world)
    day = lambda n: TEST_TODAY + timedelta(days=n)  # noqa: E731
    await _paid_until(session, world, day(14))
    await _rival(session, world, "Due later", day(15))
    await _rival(session, world, "In grace", day(-2))
    await _rival(session, world, "Read only", day(-5))
    await _rival(session, world, "Locked", day(-9))
    await _rival(session, world, "Held", day(5), hold=SubscriptionHold.SUSPENDED, hold_reason="x")
    deleted = await _rival(session, world, "Deleted", day(3))
    await client.delete(f"/api/admin/campaigns/{deleted.id}/", headers=admin_headers)

    listed = (await client.get("/api/party/finance/reports/expiring/", headers=headers)).json()

    assert [(row["title"], row["state"]) for row in listed] == [
        ("Read only", "read_only"),
        ("In grace", "grace_period"),
        ("Jane for Roysambu", "active"),
    ]


async def test_revenue_takes_both_end_days_and_deleted_campaigns(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    headers = await _finance(client, session, world)
    sub_id = await _on_plan(client, headers, world)
    await _paid_until(session, world, None)
    for n, received in enumerate(["2026-09-21", "2026-09-22", "2026-10-31", "2026-11-01"]):
        await _pay(client, headers, sub_id, f"EDGE{n}", date.fromisoformat(received))
    await client.delete(f"/api/admin/campaigns/{world.campaign.id}/", headers=admin_headers)

    report = (
        await client.get(
            "/api/party/finance/reports/revenue/?from=2026-09-22&to=2026-10-31", headers=headers
        )
    ).json()

    assert [(m["month"], m["count"]) for m in report["by_month"]] == [
        ("2026-09", 1),
        ("2026-10", 1),
    ]
    assert report["total_kes"] == 10_000
