"""A campaign made for an aspirant works exactly while that aspirant is approved."""

import httpx
import pytest
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


async def test_an_approved_aspirants_campaign_is_fully_open(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    world.campaign.signups_open = True
    await _aspirant_on(session, world, AspirantStatus.APPROVED)
    headers = world.headers("manager")

    read = await client.get("/api/supporters/", headers=headers)
    write = await client.post("/api/supporters/", headers=headers, json={})
    link = (await client.get(f"/api/join/{world.campaign.signup_code}/")).json()

    assert read.status_code == 200
    assert write.status_code == 400
    assert link["open"] is True


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/subscription/"),
        ("GET", "/api/party/finance/plans/"),
        ("GET", "/api/party/finance/subscriptions/"),
        ("GET", "/api/party/finance/settings/"),
        ("GET", "/api/party/finance/payouts/"),
        ("POST", "/api/party/finance/payouts/"),
    ],
)
async def test_the_removed_hosting_and_finance_routes_are_gone(
    client: httpx.AsyncClient, admin_headers: dict, method: str, path: str
) -> None:
    answer = await client.request(method, path, headers=admin_headers, json={})

    assert answer.status_code == 404
