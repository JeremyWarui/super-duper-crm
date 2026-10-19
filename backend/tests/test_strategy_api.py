"""The computed strategy read: the totals, the per-unit rows, and the flags."""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Event
from tests.conftest import World


async def _strategy(client: httpx.AsyncClient, world: World, role: str = "manager") -> dict:
    response = await client.get(
        f"/api/strategy/?campaign={world.campaign.id}", headers=world.headers(role)
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_the_win_number_is_the_sum_across_every_unit(
    client: httpx.AsyncClient, world: World
) -> None:
    """Zimmerman 9,211 plus Githurai 10,770."""
    body = await _strategy(client, world)

    assert body["win_number"] == 19_981
    assert body["total_registered"] == 66_600
    assert len(body["units"]) == 2


async def test_a_unit_counts_its_events_and_whether_anyone_is_working_it(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    session.add_all(
        [
            Event(campaign_id=world.campaign.id, ward_id=world.ward.id, title="One"),
            Event(campaign_id=world.campaign.id, ward_id=world.ward.id, title="Two"),
        ]
    )
    await session.commit()

    body = await _strategy(client, world)
    zimmerman = next(u for u in body["units"] if u["unit"] == "Zimmerman")
    githurai = next(u for u in body["units"] if u["unit"] == "Githurai")

    assert zimmerman["events"] == 2
    assert zimmerman["has_mobilizer"] is True
    assert githurai["events"] == 0
    assert githurai["has_mobilizer"] is False


async def test_unstaffed_units_are_flagged_by_name(client: httpx.AsyncClient, world: World) -> None:
    notes = (await _strategy(client, world))["notes"]

    unstaffed = next(n for n in notes if "unstaffed" in n["title"])
    assert unstaffed["title"] == "1 unit unstaffed"
    assert "Githurai" in unstaffed["text"]


async def test_a_mobilizer_sees_only_their_own_ward_in_the_strategy(
    client: httpx.AsyncClient, world: World
) -> None:
    body = await _strategy(client, world, "mobilizer")

    assert [u["unit"] for u in body["units"]] == ["Zimmerman"]
    assert body["win_number"] == 9_211
