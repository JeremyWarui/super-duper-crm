"""Assigning work: inside the assigner's area, marked done once, and each member sees their own."""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import CampaignMemberArea, Event, Mobilizer, UserRole
from backend.services.accounts import add_member
from tests.conftest import World
from tests.factories import auth, make_user, sign_in

URL = "/api/assignments/"


def _event_work(world: World, event: Event, mobilizer: Mobilizer, **overrides) -> dict:
    return {
        "campaign": str(world.campaign.id),
        "mobilizer": str(mobilizer.id),
        "kind": "event",
        "event": str(event.id),
        "amount_kes": 1200,
        **overrides,
    }


async def _event(session: AsyncSession, world: World, ward) -> Event:
    event = Event(campaign_id=world.campaign.id, ward_id=ward.id, title=f"Rally in {ward.name}")
    session.add(event)
    await session.commit()
    return event


async def test_a_coordinator_assigns_only_inside_their_area(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    user = await make_user(session, username="otieno", role=UserRole.COORDINATOR)
    member = await add_member(session, world.campaign.id, user)
    session.add(CampaignMemberArea(campaign_member_id=member.id, ward_id=world.ward.id))
    outsider = Mobilizer(
        campaign_id=world.campaign.id, ward_id=world.other_ward.id, full_name="Akinyi"
    )
    session.add(outsider)
    await session.commit()
    head = auth(await sign_in(client, "otieno"))
    inside = await _event(session, world, world.ward)

    allowed = await client.post(URL, headers=head, json=_event_work(world, inside, world.mobilizer))
    refused = await client.post(URL, headers=head, json=_event_work(world, inside, outsider))

    assert allowed.status_code == 201, allowed.text
    assert (allowed.json()["label"], allowed.json()["member_name"]) == (
        "Rally in Zimmerman",
        "Juma Otieno",
    )
    assert refused.status_code == 400
    assert refused.json()["detail"] == "That person works outside your area."


async def test_work_is_marked_done_once_and_its_mobilizer_sees_it(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = world.headers("manager")
    event = await _event(session, world, world.ward)
    made = (
        await client.post(URL, headers=head, json=_event_work(world, event, world.mobilizer))
    ).json()

    done = await client.post(f"{URL}{made['id']}/done/", headers=head)
    again = await client.post(f"{URL}{made['id']}/done/", headers=head)
    own = (
        await client.get(f"{URL}?campaign={world.campaign.id}", headers=world.headers("mobilizer"))
    ).json()

    assert done.json()["status"] == "done"
    assert again.status_code == 400
    assert [a["id"] for a in own] == [made["id"]]


async def test_an_activity_needs_a_description(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    body = {
        "campaign": str(world.campaign.id),
        "mobilizer": str(world.mobilizer.id),
        "kind": "activity",
        "amount_kes": 500,
    }

    bare = await client.post(URL, headers=world.headers("manager"), json=body)
    named = await client.post(
        URL, headers=world.headers("manager"), json={**body, "description": "Agent training"}
    )

    assert bare.status_code == 400
    assert named.json()["label"] == "Agent training"
