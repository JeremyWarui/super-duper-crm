"""A campaign works as far as its subscription allows on the day of the request."""

import uuid
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_today
from backend.models import (
    CampaignSubscription,
    CrmPlan,
    EntryKind,
    ReceiptMethod,
    SubscriptionEntry,
    SubscriptionHold,
    Supporter,
)
from backend.services import billing
from backend.services.billing import GRACE_DAYS, READ_ONLY_DAYS
from tests.conftest import World
from tests.factories import TEST_TODAY
from tests.test_join_api import _event, _person

ROLES = ["candidate", "manager", "mobilizer"]
READ_ONLY_SINCE = timedelta(days=GRACE_DAYS + 1)
LOCKED_SINCE = timedelta(days=GRACE_DAYS + READ_ONLY_DAYS + 1)
ANY_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def _lapse(session: AsyncSession, world: World, by: timedelta) -> None:
    world.campaign.subscription.paid_until = TEST_TODAY - by
    await session.commit()


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/supporters/"),
        ("PATCH", f"/api/supporters/{ANY_ID}/"),
        ("DELETE", f"/api/users/{ANY_ID}/"),
    ],
)
async def test_a_read_only_campaign_answers_reads_and_refuses_writes(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    method: str,
    path: str,
    role: str,
) -> None:
    await _lapse(session, world, READ_ONLY_SINCE)
    headers = world.headers(role)

    read = await client.get("/api/campaigns/", headers=headers)
    write = await client.request(method, path, headers=headers, json={})

    assert read.status_code == 200
    assert (write.status_code, write.json()["code"]) == (403, "campaign_read_only")


async def _never_paid(session: AsyncSession, world: World) -> None:
    world.campaign.subscription.paid_until = None
    await session.commit()


async def _no_subscription(session: AsyncSession, world: World) -> None:
    await session.execute(
        delete(CampaignSubscription).where(CampaignSubscription.campaign_id == world.campaign.id)
    )
    await session.commit()


async def _held(session: AsyncSession, world: World, hold: SubscriptionHold) -> None:
    world.campaign.subscription.hold = hold
    world.campaign.subscription.hold_reason = "Stopped by the finance office."
    await session.commit()


CLOSED_BY = {
    "lapsed": lambda session, world: _lapse(session, world, LOCKED_SINCE),
    "never paid": _never_paid,
    "no subscription row": _no_subscription,
    "suspended while paid": lambda session, world: _held(
        session, world, SubscriptionHold.SUSPENDED
    ),
    "cancelled while paid": lambda session, world: _held(
        session, world, SubscriptionHold.CANCELLED
    ),
}


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("cause", list(CLOSED_BY))
async def test_a_locked_campaign_refuses_everything_but_who_you_are_and_signing_out(
    client: httpx.AsyncClient, session: AsyncSession, world: World, cause: str, role: str
) -> None:
    await CLOSED_BY[cause](session, world)
    headers = world.headers(role)

    read = await client.get("/api/campaigns/", headers=headers)
    write = await client.post("/api/supporters/", headers=headers, json={})
    me = await client.get("/api/auth/me/", headers=headers)
    out = await client.post("/api/auth/logout/", headers=headers)

    assert (read.status_code, read.json()["code"]) == (403, "campaign_locked")
    assert (write.status_code, write.json()["code"]) == (403, "campaign_locked")
    assert me.status_code == 200
    assert out.status_code == 204


UNPAID_BY = {
    "read-only": lambda session, world: _lapse(session, world, READ_ONLY_SINCE),
    "never paid": _never_paid,
    "no subscription row": _no_subscription,
}


@pytest.mark.parametrize("cause", list(UNPAID_BY))
async def test_an_unpaid_campaign_takes_no_sign_ups_but_a_supporter_can_still_withdraw(
    client: httpx.AsyncClient, session: AsyncSession, world: World, cause: str
) -> None:
    event = await _event(session, world)
    url = f"/api/join/{event.signup_code}/"
    joined = (await client.post(url, json=_person())).json()

    await UNPAID_BY[cause](session, world)
    page = (await client.get(url)).json()
    refused = await client.post(url, json=_person(phone="0722 000111"))
    withdrawn = await client.post(f"/api/join/withdraw/{joined['withdraw_code']}/")
    left = await session.scalar(select(Supporter.id).where(Supporter.phone == "+254712345678"))

    assert page["open"] is False
    assert refused.status_code == 400
    assert withdrawn.status_code == 200
    assert left is None


async def test_a_locked_campaign_sees_how_to_pay_and_only_its_leaders_see_the_price(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    plan = CrmPlan(name="Monthly", price_kes=5_000, duration_days=30)
    session.add(plan)
    await session.flush()
    world.campaign.subscription.plan_id = plan.id
    await _never_paid(session, world)

    leader = (await client.get("/api/subscription/", headers=world.headers("manager"))).json()
    candidate = (await client.get("/api/subscription/", headers=world.headers("candidate"))).json()
    mobilizer = (await client.get("/api/subscription/", headers=world.headers("mobilizer"))).json()
    console = await client.get("/api/subscription/", headers=admin_headers)

    assert (leader["state"], leader["plan"]["price_kes"]) == ("pending_payment", 5_000)
    assert candidate["plan"]["price_kes"] == 5_000
    assert mobilizer["state"] == "pending_payment"
    assert (mobilizer["plan"], mobilizer["last_paid_on"], mobilizer["hold_reason"]) == (
        None,
        None,
        None,
    )
    assert console.status_code == 403


async def test_the_leaders_see_the_last_live_payment_and_why_access_is_stopped(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    plan = CrmPlan(name="Monthly", price_kes=5_000, duration_days=30)
    session.add(plan)
    await session.flush()
    sub = world.campaign.subscription
    paid = {"kind": EntryKind.PAYMENT, "plan_id": plan.id, "amount_kes": 5_000}
    paid |= {"method": ReceiptMethod.MPESA, "days": 30}
    session.add_all(
        [
            SubscriptionEntry(
                subscription_id=sub.id,
                **paid,
                reference="LIVE1",
                received_on=TEST_TODAY - timedelta(days=10),
                paid_until_after=TEST_TODAY + timedelta(days=19),
            ),
            SubscriptionEntry(
                subscription_id=sub.id,
                **paid,
                reference="VOID1",
                received_on=TEST_TODAY - timedelta(days=2),
                paid_until_after=TEST_TODAY + timedelta(days=49),
                voided_at=datetime.now(UTC),
                void_reason="Typo",
            ),
            SubscriptionEntry(
                subscription_id=sub.id,
                kind=EntryKind.EXTENSION,
                received_on=TEST_TODAY,
                days=3,
                paid_until_after=TEST_TODAY + timedelta(days=22),
                note="Goodwill",
            ),
        ]
    )
    sub.hold = SubscriptionHold.SUSPENDED
    sub.hold_reason = "Cheque bounced"
    await session.commit()

    seen = (await client.get("/api/subscription/", headers=world.headers("candidate"))).json()
    mobilizer = (await client.get("/api/subscription/", headers=world.headers("mobilizer"))).json()

    assert seen["last_paid_on"] == (TEST_TODAY - timedelta(days=10)).isoformat()
    assert (seen["state"], seen["held"], seen["hold_reason"]) == ("locked", True, "Cheque bounced")
    assert (mobilizer["held"], mobilizer["hold_reason"]) == (True, None)
    assert seen["dated_state"] == "active"


async def test_a_campaign_with_no_subscription_reads_as_locked(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await _no_subscription(session, world)

    seen = await client.get("/api/subscription/", headers=world.headers("manager"))

    assert (seen.status_code, seen.json()["state"]) == (200, "locked")


class _LateEveningUtc(datetime):
    """22:30 UTC on 1 Nov 2026, already 2 Nov in Nairobi."""

    @classmethod
    def now(cls, tz=None):
        instant = datetime(2026, 11, 1, 22, 30, tzinfo=UTC)
        return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)


async def test_today_is_the_date_in_nairobi_for_every_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(billing, "datetime", _LateEveningUtc)

    assert billing.today() == date(2026, 11, 2)
    assert await get_today() == date(2026, 11, 2)
