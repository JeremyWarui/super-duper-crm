"""A mobilizer works one ward on one campaign.

`Mobilizer.user_id` is unique, so a mobilizer has one ground row. Put on a
second campaign, their rows there would be credited to the first campaign's
ground row, which the second campaign's manager then reads.
"""

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.scope import add_member
from backend.models import Campaign, CampaignMember, OfficeLevel, UserRole
from tests.conftest import World
from tests.factories import auth, make_user, sign_in


async def _admin(session: AsyncSession, client: httpx.AsyncClient) -> dict[str, str]:
    root = await make_user(session, username="root", role=UserRole.MANAGER)
    root.is_superuser = True
    await session.commit()
    return auth(await sign_in(client, "root"))


async def _second_campaign(session: AsyncSession, world: World) -> Campaign:
    """A county race whose area covers the mobilizer's own ward."""
    boss = await make_user(session, username="countyboss", role=UserRole.CANDIDATE)
    race = Campaign(
        title="Nairobi Governor",
        office_level=OfficeLevel.COUNTY,
        county_id=world.county.id,
    )
    session.add(race)
    await session.flush()
    await add_member(session, race.id, boss.id)
    await session.commit()
    return race


async def _stale_second_membership(session: AsyncSession, world: World) -> Campaign:
    """A membership no route makes, which a database from before the rule may hold."""
    second = await _second_campaign(session, world)
    session.add(
        CampaignMember(
            campaign_id=second.id, user_id=world.mobilizer_user.id, role=UserRole.MOBILIZER
        )
    )
    await session.commit()
    return second


async def test_the_console_will_not_put_a_mobilizer_on_a_second_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)
    second = await _second_campaign(session, world)

    refused = await client.post(
        f"/api/admin/campaigns/{second.id}/members/",
        headers=head,
        json={"user": str(world.mobilizer_user.id)},
    )

    assert refused.status_code == 400
    assert "another campaign" in refused.json()["detail"]
    on_second = await session.scalar(
        select(CampaignMember).where(
            CampaignMember.campaign_id == second.id,
            CampaignMember.user_id == world.mobilizer_user.id,
        )
    )
    assert on_second is None


async def test_no_route_can_put_a_mobilizer_on_a_second_campaign(
    session: AsyncSession, world: World
) -> None:
    second = await _second_campaign(session, world)

    with pytest.raises(HTTPException) as refused:
        await add_member(session, second.id, world.mobilizer_user.id)

    assert refused.value.status_code == 400


async def test_a_mobilizer_is_still_put_back_on_their_own_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """The rule is about a second campaign, not about the one they work."""
    head = await _admin(session, client)

    again = await client.post(
        f"/api/admin/campaigns/{world.campaign.id}/members/",
        headers=head,
        json={"user": str(world.mobilizer_user.id)},
    )

    assert again.status_code == 201, again.text


async def test_a_mobilizer_s_own_supporter_is_still_credited_to_them(
    client: httpx.AsyncClient, world: World
) -> None:
    made = await client.post(
        "/api/supporters/",
        headers=world.headers("mobilizer"),
        json={
            "campaign": str(world.campaign.id),
            "full_name": "Own Work",
            "phone": "+254700333444",
            "support_level": "supporter",
            "consent_given": True,
        },
    )

    assert made.status_code == 201, made.text
    assert made.json()["mobilizer"] == str(world.mobilizer.id)


async def test_a_supporter_on_another_campaign_is_not_credited_to_this_ones_ground_row(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    second = await _stale_second_membership(session, world)

    made = await client.post(
        "/api/supporters/",
        headers=world.headers("mobilizer"),
        json={
            "campaign": str(second.id),
            "full_name": "Cross Filed",
            "phone": "+254700333555",
            "support_level": "supporter",
            "consent_given": True,
        },
    )

    assert made.status_code == 201, made.text
    assert made.json()["mobilizer"] is None


async def test_an_event_on_another_campaign_is_not_credited_to_this_ones_ground_row(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    second = await _stale_second_membership(session, world)

    made = await client.post(
        "/api/events/",
        headers=world.headers("mobilizer"),
        json={
            "campaign": str(second.id),
            "ward": str(world.ward.id),
            "title": "Cross rally",
            "venue": "Hall",
        },
    )

    assert made.status_code == 201, made.text
    assert made.json()["mobilizer"] is None
