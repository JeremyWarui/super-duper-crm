"""A ward or centre named in a request must lie inside the campaign's seat."""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Constituency,
    Event,
    Mobilizer,
    Supporter,
    Ward,
)
from tests.conftest import World

OUTSIDE = "That ward is not one this campaign works."


async def _elsewhere(session: AsyncSession, world: World) -> Ward:
    """A ward in another constituency of the same county, which no target covers."""
    other = Constituency(county_id=world.county.id, name="Kasarani", code="281")
    ward = Ward(constituency=other, name="Mwiki", code="1450", registered_voters=21_000)
    session.add_all([other, ward])
    await session.commit()
    return ward


async def test_a_mobilizer_cannot_be_put_on_a_ward_outside_the_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    outside = await _elsewhere(session, world)

    refused = await client.post(
        "/api/mobilizers/",
        headers=world.headers("manager"),
        json={
            "campaign": str(world.campaign.id),
            "ward": str(outside.id),
            "full_name": "Stray Boots",
        },
    )

    assert refused.status_code == 400
    assert refused.json()["detail"] == OUTSIDE
    assert (
        await session.scalar(select(Mobilizer).where(Mobilizer.full_name == "Stray Boots")) is None
    )


async def test_a_supporter_cannot_be_registered_in_a_ward_outside_the_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    outside = await _elsewhere(session, world)

    refused = await client.post(
        "/api/supporters/",
        headers=world.headers("manager"),
        json={
            "campaign": str(world.campaign.id),
            "ward": str(outside.id),
            "full_name": "Ghost Voter",
            "phone": "+254700111333",
            "support_level": "supporter",
            "consent_given": True,
        },
    )

    assert refused.status_code == 400
    assert refused.json()["detail"] == OUTSIDE
    assert (
        await session.scalar(select(Supporter).where(Supporter.full_name == "Ghost Voter")) is None
    )


async def test_a_centre_has_to_be_in_the_ward_it_is_named_with(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """Both wards are the campaign's; the centre belongs to only one of them."""
    refused = await client.post(
        "/api/events/",
        headers=world.headers("manager"),
        json={
            "campaign": str(world.campaign.id),
            "ward": str(world.other_ward.id),
            "registration_centre": str(world.centre.id),
            "title": "Crossed wires",
            "venue": "Githurai",
        },
    )

    assert refused.status_code == 400
    assert refused.json()["detail"] == "That registration centre is not in that ward."
    assert await session.scalar(select(Event).where(Event.title == "Crossed wires")) is None
