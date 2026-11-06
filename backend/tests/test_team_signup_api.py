"""Team sign-up: pending logins, decisions by area, unique phone and ID, hidden ID numbers,
approval with an invite, and agent coverage."""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Agent,
    CampaignMemberArea,
    Mobilizer,
    TeamRegistration,
    User,
    UserRole,
)
from backend.security import hash_password
from backend.services.accounts import add_member
from tests.conftest import World
from tests.factories import TEST_PASSWORD, auth, claim_link, make_user, sign_in


def _signup(world: World, **overrides) -> dict:
    body = {
        "role": "mobilizer",
        "first_name": "Achieng",
        "last_name": "Otieno",
        "phone": "0712 345001",
        "email": "achieng@example.test",
        "id_number": "12345678",
        "ward": str(world.other_ward.id),
        "consent_given": True,
    }
    return {**body, **overrides}


async def _sign_up(client: httpx.AsyncClient, world: World, **overrides) -> httpx.Response:
    return await client.post(
        f"/api/team-signup/{world.campaign.team_code}/", json=_signup(world, **overrides)
    )


async def _agent_signup(client: httpx.AsyncClient, world: World, **overrides) -> httpx.Response:
    return await _sign_up(
        client,
        world,
        role="agent",
        ward=None,
        registration_centre=str(world.centre.id),
        email="agent@example.test",
        phone="0712 345002",
        id_number="87654321",
        **overrides,
    )


async def _registration(session: AsyncSession, email: str) -> TeamRegistration:
    return await session.scalar(select(TeamRegistration).where(TeamRegistration.email == email))


async def _coordinator(session: AsyncSession, client: httpx.AsyncClient, world: World) -> dict:
    """A coordinator whose area is Zimmerman, signed in."""
    user = await make_user(session, username="otieno", role=UserRole.COORDINATOR)
    member = await add_member(session, world.campaign.id, user)
    session.add(CampaignMemberArea(campaign_member_id=member.id, ward_id=world.ward.id))
    await session.commit()
    return auth(await sign_in(client, "otieno"))


def _queue(world: World, *rest: str) -> str:
    return "/".join([f"/api/campaigns/{world.campaign.id}/registrations", *rest, ""])


async def test_the_page_offers_the_seats_wards_and_a_wards_centres(
    client: httpx.AsyncClient, world: World
) -> None:
    page = await client.get(f"/api/team-signup/{world.campaign.team_code}/")
    centres = await client.get(
        f"/api/team-signup/{world.campaign.team_code}/centres/?ward={world.ward.id}"
    )

    assert page.status_code == 200, page.text
    assert {w["name"] for w in page.json()["wards"]} == {"Zimmerman", "Githurai"}
    assert page.json()["mobilizer_place"] == "ward"
    assert [c["name"] for c in centres.json()] == ["Zimmerman Primary"]
    assert (await client.get("/api/team-signup/nope/")).status_code == 404


async def test_a_sign_up_makes_a_pending_login_that_cannot_sign_in(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    response = await _sign_up(client, world)
    login = await session.scalar(select(User).where(User.email == "achieng@example.test"))
    login.password_hash = hash_password(TEST_PASSWORD)
    await session.commit()

    tried = await client.post(
        "/api/auth/login/", json={"email": "achieng@example.test", "password": TEST_PASSWORD}
    )

    assert response.status_code == 201, response.text
    assert (login.pending, login.is_active, login.role) == (True, False, UserRole.MOBILIZER)
    assert tried.status_code == 400


async def test_a_duplicate_phone_or_id_number_in_the_same_workspace_is_refused(
    client: httpx.AsyncClient, world: World
) -> None:
    await _sign_up(client, world)

    same_phone = await _sign_up(client, world, email="b@example.test", id_number="99999999")
    same_id = await _sign_up(client, world, email="c@example.test", phone="0799 000111")

    assert same_phone.status_code == 400
    assert same_phone.json()["detail"] == "That phone number is already signed up to this team."
    assert same_id.status_code == 400
    assert same_id.json()["detail"] == "That ID number is already signed up to this team."


async def test_a_coordinator_decides_only_sign_ups_in_their_area(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _coordinator(session, client, world)
    await _sign_up(client, world)  # Githurai, outside the area
    await _agent_signup(client, world)  # Zimmerman Primary, inside
    outside = await _registration(session, "achieng@example.test")
    inside = await _registration(session, "agent@example.test")

    listed = await client.get(_queue(world), headers=head)
    refused = await client.post(_queue(world, str(outside.id), "approve"), headers=head)
    approved = await client.post(_queue(world, str(inside.id), "approve"), headers=head)

    assert [r["full_name"] for r in listed.json()] == ["Achieng Otieno"]
    assert listed.json()[0]["role"] == "agent"
    assert refused.status_code == 404
    assert approved.status_code == 200, approved.text


async def test_an_id_number_reaches_no_role_without_team_id_read(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _coordinator(session, client, world)
    await _agent_signup(client, world)
    row = await _registration(session, "agent@example.test")
    await client.post(_queue(world, str(row.id), "approve"), headers=world.headers("manager"))
    agents = f"/api/agents/?campaign={world.campaign.id}"

    coordinator_queue = (await client.get(_queue(world), headers=head)).json()
    coordinator_agents = (await client.get(agents, headers=head)).json()
    manager_agents = (await client.get(agents, headers=world.headers("manager"))).json()
    agent_head = auth(await claim_link(client, session, "agent@example.test"))
    own = (await client.get(agents, headers=agent_head)).json()

    assert [r["id_number"] for r in coordinator_queue] == [None]
    assert [a["id_number"] for a in coordinator_agents] == [None]
    assert [a["id_number"] for a in manager_agents] == ["87654321"]
    assert [a["id_number"] for a in own] == ["87654321"]


async def test_approval_activates_the_login_places_it_and_emails_an_invite(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await _sign_up(client, world)
    row = await _registration(session, "achieng@example.test")

    approved = await client.post(
        _queue(world, str(row.id), "approve"), headers=world.headers("candidate")
    )
    head = auth(await claim_link(client, session, "achieng@example.test"))
    mobilizer = await session.scalar(select(Mobilizer).where(Mobilizer.user_id == row.user_id))

    assert approved.status_code == 200, approved.text
    assert (approved.json()["invite"], approved.json()["placed"]) == ("email", True)
    assert approved.json()["registration"]["status"] == "approved"
    assert mobilizer.ward_id == world.other_ward.id
    assert (await client.get("/api/campaigns/", headers=head)).status_code == 200


async def test_rejection_needs_a_reason_and_deletes_the_login(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await _sign_up(client, world)
    row = await _registration(session, "achieng@example.test")
    login_id = row.user_id

    bare = await client.post(
        _queue(world, str(row.id), "reject"), headers=world.headers("manager"), json={"reason": ""}
    )
    rejected = await client.post(
        _queue(world, str(row.id), "reject"),
        headers=world.headers("manager"),
        json={"reason": "Not known to the ward team."},
    )
    gone = await session.scalar(select(User).where(User.id == login_id))
    again = await _sign_up(client, world)

    assert bare.status_code == 400
    assert rejected.json()["status"] == "rejected"
    assert gone is None
    assert again.status_code == 201, again.text


async def test_coverage_counts_centres_with_an_agent(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await _agent_signup(client, world)
    row = await _registration(session, "agent@example.test")
    before = await client.get(
        f"/api/agents/coverage/?campaign={world.campaign.id}", headers=world.headers("manager")
    )
    await client.post(_queue(world, str(row.id), "approve"), headers=world.headers("manager"))
    after = await client.get(
        f"/api/agents/coverage/?campaign={world.campaign.id}", headers=world.headers("manager")
    )
    agent = await session.scalar(select(Agent).where(Agent.user_id == row.user_id))

    assert (before.json()["centres"], before.json()["covered"]) == (1, 0)
    assert [c["name"] for c in before.json()["uncovered"]] == ["Zimmerman Primary"]
    assert (after.json()["covered"], after.json()["uncovered"]) == (1, [])
    assert agent.registration_centre_id == world.centre.id


async def test_a_sign_up_decided_after_it_was_read_is_not_decided_again(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    from sqlalchemy import update

    from backend.models import RegistrationStatus
    from backend.services import team_signup
    from backend.services.errors import Refused

    await _sign_up(client, world)
    row = await _registration(session, "achieng@example.test")
    await session.execute(
        update(TeamRegistration)
        .where(TeamRegistration.id == row.id)
        .values(status=RegistrationStatus.REJECTED)
        .execution_options(synchronize_session=False)
    )
    try:
        await team_signup.approve(session, world.campaign, row, actor=world.manager)
    except Refused:
        refused = True
    else:
        refused = False

    assert refused
