"""Announcements and calls for one registration centre's team."""

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Agent,
    CampaignMember,
    CampaignMemberArea,
    Mobilizer,
    Notice,
    RegistrationCentre,
    UserRole,
)
from backend.services.accounts import add_member
from tests.conftest import World
from tests.factories import make_user, sign_in
from tests.test_meetings import Rooms, livekit, start  # noqa: F401


async def centre_teams(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> tuple[RegistrationCentre, dict]:
    """Two centres in the staffed ward, each with its own mobilizer login."""
    other = RegistrationCentre(
        ward_id=world.ward.id, name="Kahawa West Primary", code="902", registered_voters=900
    )
    session.add(other)
    await session.flush()
    headers = {}
    for username, centre in (("wanjiru", world.centre), ("otieno", other)):
        user = await make_user(session, username=username, role=UserRole.MOBILIZER)
        await add_member(session, world.campaign.id, user)
        session.add(
            Mobilizer(
                campaign_id=world.campaign.id,
                ward_id=world.ward.id,
                registration_centre_id=centre.id,
                full_name=username.title(),
                user_id=user.id,
            )
        )
        await session.commit()
        headers[username] = {"Authorization": f"Token {await sign_in(client, username)}"}
    return other, headers


async def test_an_announcement_reaches_one_centres_team_and_counts_who_read_it(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    _, headers = await centre_teams(client, session, world)
    url = f"/api/campaigns/{world.campaign.id}/announcements/"

    sent = await client.post(
        url,
        json={
            "title": "Briefing at 6pm",
            "body": "Bring the register.",
            "centre": str(world.centre.id),
        },
        headers=world.headers("manager"),
    )
    there = await client.get(url, headers=headers["wanjiru"])
    elsewhere = await client.get(url, headers=headers["otieno"])
    ward_level = await client.get(url, headers=world.headers("mobilizer"))
    await client.post(url + "read/", headers=headers["wanjiru"])
    receipts = (await client.get(url, headers=world.headers("manager"))).json()[0]
    lead = (await client.get(url, headers=world.headers("candidate"))).json()[0]

    assert sent.status_code == 201, sent.text
    assert sent.json()["announcement"]["unit"] == f"{world.centre.name} centre"
    assert [a["title"] for a in there.json()] == ["Briefing at 6pm"]
    assert there.json()[0]["read_by_me"] is False
    assert elsewhere.json() == [] and ward_level.json() == []
    # The candidate and the centre's mobilizer; the manager sent it.
    assert (receipts["read"], receipts["recipients"]) == (1, 2)
    # Another lead, who may announce there too, sees the receipts as well.
    assert (lead["read"], lead["recipients"]) == (1, 2)


async def test_a_centre_reaches_a_constituency_coordinator_but_not_a_removed_agent(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    coordinator = await make_user(session, username="kamau", role=UserRole.COORDINATOR)
    member = await add_member(session, world.campaign.id, coordinator)
    await session.execute(
        delete(CampaignMemberArea).where(CampaignMemberArea.campaign_member_id == member.id)
    )
    session.add(
        CampaignMemberArea(campaign_member_id=member.id, constituency_id=world.ward.constituency_id)
    )
    agent = await make_user(session, username="akinyi", role=UserRole.AGENT)
    await add_member(session, world.campaign.id, agent)
    session.add(
        Agent(
            campaign_id=world.campaign.id,
            user_id=agent.id,
            ward_id=world.ward.id,
            registration_centre_id=world.centre.id,
        )
    )
    await session.commit()
    await session.execute(delete(CampaignMember).where(CampaignMember.user_id == agent.id))
    await session.commit()

    sent = await client.post(
        f"/api/campaigns/{world.campaign.id}/announcements/",
        json={"title": "Count day plan", "body": "Read it.", "centre": str(world.centre.id)},
        headers=world.headers("manager"),
    )

    assert sent.status_code == 201, sent.text
    told = set(await session.scalars(select(Notice.user_id)))
    assert coordinator.id in told
    assert agent.id not in told


async def test_a_call_for_a_centre_is_listed_under_that_centre(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    livekit: Rooms,  # noqa: F811
) -> None:
    await start(client, world, centre=str(world.centre.id))

    calls = await client.get(
        f"/api/campaigns/{world.campaign.id}/meetings/", headers=world.headers("manager")
    )

    assert calls.json()[0]["unit"] == f"{world.centre.name} centre"
    assert calls.json()[0]["meeting"]["centre"] == str(world.centre.id)
