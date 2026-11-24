"""Campaign events on the public website: the CRM's events are the one list."""

from datetime import UTC, date, datetime, timedelta

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_today
from backend.main import app
from backend.models import Event, EventStatus
from tests.conftest import World

TODAY = date(2026, 11, 25)


def at(days: int) -> datetime:
    return datetime(2026, 11, 25, 9, tzinfo=UTC) + timedelta(days=days)


async def test_only_published_upcoming_events_reach_the_website(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    def event(title: str, days: int, published: bool, signups_open: bool = True) -> Event:
        return Event(
            campaign_id=world.campaign.id,
            ward_id=world.ward.id,
            title=title,
            venue="Zimmerman grounds",
            scheduled_date=at(days),
            published=published,
            signups_open=signups_open,
        )

    rally, forum = event("Rally", 3, True), event("Forum", 1, True, signups_open=False)
    session.add_all([rally, forum, event("Team briefing", 2, False), event("Old rally", -2, True)])
    await session.commit()
    app.dependency_overrides[get_today] = lambda: TODAY
    try:
        listed = (await client.get("/api/website/events/")).json()
        hidden = await client.get(f"/api/website/events/{forum.id}/")
    finally:
        app.dependency_overrides.pop(get_today, None)

    assert [e["title"] for e in listed] == ["Forum", "Rally"]
    assert [e["signup_code"] for e in listed] == [None, rally.signup_code]
    assert listed[1]["ward_name"] == world.ward.name
    assert "number_reached" not in listed[0]
    assert hidden.status_code == 200


async def test_only_those_who_edit_the_website_put_an_event_on_it(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    rally = Event(campaign_id=world.campaign.id, ward_id=world.ward.id, title="Rally")
    session.add(rally)
    await session.commit()
    body = {"published": True, "description": "Come early."}

    refused = await client.post(
        f"/api/events/{rally.id}/website/", json=body, headers=world.headers("mobilizer")
    )
    shown = await client.post(
        f"/api/events/{rally.id}/website/", json=body, headers=world.headers("manager")
    )

    assert refused.status_code == 403
    assert shown.status_code == 200, shown.text
    assert (shown.json()["published"], shown.json()["description"]) == (True, "Come early.")


async def test_a_cancelled_event_leaves_the_website(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    called_off = Event(
        campaign_id=world.campaign.id,
        ward_id=world.ward.id,
        title="Called off",
        scheduled_date=at(2),
        published=True,
        status=EventStatus.CANCELLED,
    )
    session.add(called_off)
    await session.commit()
    app.dependency_overrides[get_today] = lambda: TODAY
    try:
        listed = (await client.get("/api/website/events/")).json()
        one = await client.get(f"/api/website/events/{called_off.id}/")
    finally:
        app.dependency_overrides.pop(get_today, None)

    assert listed == []
    assert one.status_code == 404
