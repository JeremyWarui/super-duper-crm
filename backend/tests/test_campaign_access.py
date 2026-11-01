"""A campaign made for an aspirant works only while that aspirant is approved."""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Aspirant, AspirantStatus, PartyRoleName, Seat
from tests.conftest import World
from tests.factories import make_officer


async def _aspirant_on(session: AsyncSession, world: World, status: AspirantStatus) -> Aspirant:
    member_id = (
        await make_officer(session, world.ward, PartyRoleName.MEMBERSHIP_OFFICER)
    ).party_member_id
    aspirant = Aspirant(
        member_id=member_id,
        seat=Seat.MP,
        constituency_id=world.constituency.id,
        status=status,
        campaign_id=world.campaign.id,
    )
    session.add(aspirant)
    await session.commit()
    return aspirant


async def test_a_suspended_aspirants_campaign_is_closed_until_reinstated(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    aspirant = await _aspirant_on(session, world, AspirantStatus.SUSPENDED)
    headers = world.headers("manager")

    closed = await client.get("/api/campaigns/", headers=headers)
    me = await client.get("/api/auth/me/", headers=headers)
    aspirant.status = AspirantStatus.APPROVED
    await session.commit()
    reopened = await client.get("/api/campaigns/", headers=headers)

    assert (closed.status_code, closed.json()["code"]) == (403, "campaign_suspended")
    assert me.status_code == 200
    assert reopened.status_code == 200
    assert (await client.post("/api/auth/logout/", headers=headers)).status_code == 204


async def test_a_suspended_aspirants_sign_up_link_is_closed(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    world.campaign.signups_open = True
    await session.commit()
    url = f"/api/join/{world.campaign.signup_code}/"
    before = (await client.get(url)).json()["open"]

    await _aspirant_on(session, world, AspirantStatus.SUSPENDED)

    assert before is True
    assert (await client.get(url)).json()["open"] is False
