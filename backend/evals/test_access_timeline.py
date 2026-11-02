"""Walk a lapsing subscription day by day: the state, the API's answers and whether the
sign-up link is open match the design.

docs/Subscriptions_Design.md, "Access state": active through the last paid day, then
`grace_days` of full access, then `read_only_days` of reads only, then locked.
"""

from datetime import date, timedelta

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_today
from backend.main import app
from backend.models import AccessState, PartySettings, SubscriptionHold
from backend.services.billing import access
from tests.conftest import World
from tests.test_join_api import _event

PAID_UNTIL = date(2026, 11, 30)


def expected(day: date, grace_days: int, read_only_days: int) -> AccessState:
    lapsed = (day - PAID_UNTIL).days
    if lapsed <= 0:
        return AccessState.ACTIVE
    if lapsed <= grace_days:
        return AccessState.GRACE_PERIOD
    if lapsed <= grace_days + read_only_days:
        return AccessState.READ_ONLY
    return AccessState.LOCKED


# A read, a write, and whether the public sign-up link is open.
ANSWERS = {
    AccessState.ACTIVE: ((200, None), (400, None), True),
    AccessState.GRACE_PERIOD: ((200, None), (400, None), True),
    AccessState.READ_ONLY: ((200, None), (403, "campaign_read_only"), False),
    AccessState.LOCKED: ((403, "campaign_locked"), (403, "campaign_locked"), False),
}


def _answer(response: httpx.Response) -> tuple[int, str | None]:
    code = response.json().get("code") if response.status_code == 403 else None
    return response.status_code, code


@pytest.mark.parametrize(("grace_days", "read_only_days"), [(7, 7), (0, 7), (7, 0), (0, 0)])
async def test_each_day_of_a_lapse_answers_as_the_design_says(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    grace_days: int,
    read_only_days: int,
) -> None:
    session.add(
        PartySettings(id=1, name="Party", grace_days=grace_days, read_only_days=read_only_days)
    )
    world.campaign.subscription.paid_until = PAID_UNTIL
    await session.commit()
    headers = world.headers("manager")
    link = f"/api/join/{(await _event(session, world)).signup_code}/"

    seen, wanted = [], []
    for offset in range(-1, grace_days + read_only_days + 2):
        day = PAID_UNTIL + timedelta(days=offset)
        app.dependency_overrides[get_today] = lambda day=day: day
        state = expected(day, grace_days, read_only_days)
        read = await client.get("/api/supporters/", headers=headers)
        write = await client.post("/api/supporters/", headers=headers, json={})
        signup = (await client.get(link)).json()["open"]
        computed = access(PAID_UNTIL, SubscriptionHold.NONE, day, grace_days, read_only_days)
        seen.append((day, computed.state, _answer(read), _answer(write), signup))
        wanted.append((day, state, *ANSWERS[state]))

    assert seen == wanted
