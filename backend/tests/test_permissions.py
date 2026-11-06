"""The permissions map (docs/Product_Design.md, section 0.2) against the real routes, and the
coordinator's area."""

import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import CampaignMemberArea, OrganisationType, Supporter, UserRole
from backend.services.accounts import add_member
from backend.services.permissions import MAP
from tests.conftest import World
from tests.factories import TEST_PASSWORD, auth, email_of, make_user, sign_in

C, M, CO, CM, MO, AG = (
    "candidate",
    "manager",
    "coordinator",
    "comms",
    "mobilizer",
    "agent",
)

# Section 0.2 for every action a route serves today; the Mobilizer reads targets in their ward.
TABLE = {
    "strategy.read": {C, M, CO},
    "targets.read": {C, M, CO, MO},
    "targets.write": {C, M},
    "team.manager": {C},
    "team.write": {C, M},
    "team.approve": {C, M, CO},
    "team.id_read": {C, M, MO, AG},
    "agents.read": {C, M, CO, AG},
    "agents.write": {C, M, CO},
    "mobilizers.read": {C, M, CO, MO},
    "mobilizers.write": {C, M, CO},
    "supporters.read": {C, M, CO, MO},
    "supporters.write": {C, M, CO, MO},
    "events.read": {C, M, CO, CM, MO, AG},
    "events.write": {C, M, CO, MO},
    "payments.read": {C, M, CO, MO, AG},
    "payments.schedule": {M, CO},
    "payments.approve": {C, M},
    "assignments.read": {C, M, CO, MO, AG},
    "assignments.write": {C, M, CO},
    "sms.draft": {C, M, CO, CM},
    "sms.send": {C, M},
    "site.write": {C, M, CM},
    "volunteers.read": {C, M, CO},
    "volunteers.write": {C, M, CO},
    "export": {C, M},
    "party.feed": {C, M, CM},
    "sharing.write": {C},
}
NOBODY = str(uuid.UUID(int=1))


def _route(action: str, campaign: uuid.UUID, event: uuid.UUID) -> tuple[str, str, dict | None]:
    """One route serving the action; a write sends an empty body, which a permitted caller
    gets back as 400."""
    return {
        "strategy.read": ("GET", f"/api/strategy/?campaign={campaign}", None),
        "targets.read": ("GET", f"/api/targets/?campaign={campaign}", None),
        "targets.write": ("POST", "/api/targets/", {}),
        "team.manager": ("POST", f"/api/campaigns/{campaign}/team/manager/", {}),
        "team.write": ("GET", f"/api/campaigns/{campaign}/team/", None),
        "team.approve": ("GET", f"/api/campaigns/{campaign}/registrations/", None),
        "agents.read": ("GET", f"/api/agents/?campaign={campaign}", None),
        "agents.write": ("PATCH", f"/api/agents/{NOBODY}/", {}),
        "export": ("GET", f"/api/agents/export/?campaign={campaign}", None),
        "mobilizers.read": ("GET", f"/api/mobilizers/?campaign={campaign}", None),
        "mobilizers.write": ("POST", "/api/mobilizers/", {}),
        "supporters.read": ("GET", "/api/supporters/", None),
        "supporters.write": ("POST", "/api/supporters/", {}),
        "events.read": ("GET", "/api/events/", None),
        "events.write": ("POST", "/api/events/", {}),
        "payments.read": ("GET", "/api/payments/", None),
        "payments.schedule": ("POST", "/api/payments/", {}),
        "payments.approve": ("POST", f"/api/payments/{NOBODY}/release/", None),
        "assignments.read": ("GET", f"/api/assignments/?campaign={campaign}", None),
        "assignments.write": ("POST", "/api/assignments/", {}),
        "sms.draft": ("GET", f"/api/messages/?campaign={campaign}", None),
        "sms.send": ("POST", f"/api/messages/{NOBODY}/send/", None),
        "site.write": ("GET", "/api/workspace/site/posts/", None),
        "volunteers.read": ("GET", f"/api/campaigns/{campaign}/volunteers/", None),
        "volunteers.write": ("PATCH", f"/api/campaigns/{campaign}/volunteers/{NOBODY}/", {}),
        "party.feed": ("GET", f"/api/party-feed/?campaign={campaign}", None),
        "sharing.write": ("PUT", f"/api/party-feed/sharing/?campaign={campaign}", {}),
    }[action]


async def _join(
    session: AsyncSession, client: httpx.AsyncClient, world: World, role: UserRole
) -> tuple[uuid.UUID, dict[str, str]]:
    """A login in this role on the world's campaign; its member id and headers."""
    user = await make_user(session, username=role.value, role=role)
    member = await add_member(session, world.campaign.id, user)
    await session.commit()
    return member.id, auth(await sign_in(client, role.value))


@pytest.fixture
async def everyone(
    session: AsyncSession, client: httpx.AsyncClient, world: World
) -> dict[str, dict[str, str]]:
    """Headers for all six roles; the coordinator's area is Zimmerman."""
    heads = {role: world.headers(role) for role in (C, M, MO)}
    for role in (UserRole.COORDINATOR, UserRole.COMMS, UserRole.AGENT):
        member_id, heads[role.value] = await _join(session, client, world, role)
        if role is UserRole.COORDINATOR:
            session.add(CampaignMemberArea(campaign_member_id=member_id, ward_id=world.ward.id))
            await session.commit()
    return heads


def test_the_map_is_section_0_2() -> None:
    assert {action: {role.value for role in roles} for action, roles in MAP.items()} == TABLE


async def test_every_role_reaches_exactly_the_routes_the_map_gives_it(
    session: AsyncSession,
    client: httpx.AsyncClient,
    world: World,
    everyone: dict[str, dict[str, str]],
    organisation_type: OrganisationType,
) -> None:
    from backend.models import Event

    event = Event(campaign_id=world.campaign.id, ward_id=world.ward.id, title="Rally")
    session.add(event)
    await session.commit()
    # The workspace website exists only in an aspirant installation.
    table = {
        action: roles
        for action, roles in TABLE.items()
        if action != "site.write" or organisation_type is OrganisationType.ASPIRANT
        # A field rule, not a route: tested in test_team_signup_api.py.
        if action != "team.id_read"
    }
    allowed = {}
    for action in table:
        method, url, body = _route(action, world.campaign.id, event.id)
        allowed[action] = {
            role
            for role, head in everyone.items()
            if (await client.request(method, url, headers=head, json=body)).status_code != 403
        }

    assert allowed == table


async def _supporter(session: AsyncSession, world: World, name: str, ward) -> Supporter:
    supporter = Supporter(
        campaign_id=world.campaign.id, ward_id=ward.id, full_name=name, phone=f"+2547{name}"
    )
    session.add(supporter)
    await session.commit()
    return supporter


async def test_a_coordinator_never_reads_or_writes_a_supporter_outside_their_area(
    session: AsyncSession,
    client: httpx.AsyncClient,
    world: World,
    everyone: dict[str, dict[str, str]],
) -> None:
    await _supporter(session, world, "00000001", world.ward)
    outside = await _supporter(session, world, "00000002", world.other_ward)
    head = everyone[CO]

    listed = (await client.get("/api/supporters/", headers=head)).json()
    moved = await client.patch(
        f"/api/supporters/{outside.id}/",
        headers=head,
        json={"registration_centre": str(world.centre.id)},
    )
    added = await client.post(
        "/api/supporters/",
        headers=head,
        json={
            "campaign": str(world.campaign.id),
            "ward": str(world.other_ward.id),
            "full_name": "Otieno K.",
            "phone": "+254700555666",
            "support_level": "supporter",
            "consent_given": True,
        },
    )

    assert [s["ward"] for s in listed] == [str(world.ward.id)]
    assert (moved.status_code, added.status_code) == (403, 403)
    assert added.json()["detail"] == "That is outside your area."


async def test_a_payment_a_coordinator_schedules_needs_the_manager_to_release_it(
    session: AsyncSession,
    client: httpx.AsyncClient,
    world: World,
    everyone: dict[str, dict[str, str]],
) -> None:
    from datetime import UTC, datetime

    from backend.models import Assignment, AssignmentKind, AssignmentStatus, Event, EventStatus

    event = Event(
        campaign_id=world.campaign.id,
        ward_id=world.ward.id,
        mobilizer_id=world.mobilizer.id,
        title="Rally",
        status=EventStatus.DONE,
        scheduled_date=datetime(2027, 1, 1, tzinfo=UTC),
    )
    world.mobilizer.phone = "0712345678"
    session.add(event)
    await session.flush()
    work = Assignment(
        campaign_id=world.campaign.id,
        mobilizer_id=world.mobilizer.id,
        kind=AssignmentKind.EVENT,
        event_id=event.id,
        ward_id=world.ward.id,
        amount_kes=500,
        status=AssignmentStatus.DONE,
    )
    session.add(work)
    await session.commit()

    scheduled = await client.post(
        "/api/payments/", headers=everyone[CO], json={"assignment": str(work.id)}
    )
    url = f"/api/payments/{scheduled.json()['id']}/release/"
    by_coordinator = await client.post(url, headers=everyone[CO])
    by_manager = await client.post(url, headers=everyone[M])

    assert scheduled.status_code == 201
    assert by_coordinator.status_code == 403
    assert by_manager.status_code == 200


async def test_comms_reads_events_without_their_sign_up_code(
    client: httpx.AsyncClient, world: World, everyone: dict[str, dict[str, str]]
) -> None:
    created = await client.post(
        "/api/events/",
        headers=everyone[M],
        json={"campaign": str(world.campaign.id), "ward": str(world.ward.id), "title": "Rally"},
    )

    (event,) = (await client.get("/api/events/", headers=everyone[CM])).json()

    assert created.status_code == 201
    assert (event["title"], event["signup_code"]) == ("Rally", None)


async def test_the_candidate_adds_a_coordinator_and_gives_them_an_area(
    client: httpx.AsyncClient, world: World
) -> None:
    team = f"/api/campaigns/{world.campaign.id}/team/"
    head = world.headers(C)
    added = await client.post(
        team, headers=head, json={"username": "otieno", "role": "coordinator"}
    )
    comms = await client.post(team, headers=head, json={"username": "akinyi", "role": "comms"})
    area = {"wards": [str(world.ward.id)], "registration_centres": [str(world.centre.id)]}

    set_area = await client.put(f"{team}{added.json()['id']}/area/", headers=head, json=area)
    read = await client.get(f"{team}{added.json()['id']}/area/", headers=head)
    on_comms = await client.put(f"{team}{comms.json()['id']}/area/", headers=head, json=area)
    outside = await client.put(
        f"{team}{added.json()['id']}/area/",
        headers=head,
        json={"wards": [str(uuid.UUID(int=7))]},
    )

    assert (added.status_code, added.json()["role"]) == (201, "coordinator")
    assert set_area.json() == read.json() == area
    assert (on_comms.status_code, on_comms.json()["detail"]) == (
        400,
        "Only a coordinator has an area.",
    )
    assert outside.status_code == 400


async def test_a_pending_login_cannot_sign_in(
    session: AsyncSession, client: httpx.AsyncClient
) -> None:
    await make_user(session, username="wanjiru", role=UserRole.AGENT, pending=True, is_active=False)

    answer = await client.post(
        "/api/auth/login/", json={"email": email_of("wanjiru"), "password": TEST_PASSWORD}
    )

    assert answer.status_code == 400
    assert "token" not in answer.json()


@pytest.mark.parametrize("route", ["payment", "event", "supporter"])
async def test_a_coordinator_cannot_credit_or_pay_a_mobilizer_outside_their_area(
    session: AsyncSession,
    client: httpx.AsyncClient,
    world: World,
    everyone: dict[str, dict[str, str]],
    route: str,
) -> None:
    from datetime import UTC, datetime

    from backend.models import (
        Assignment,
        AssignmentKind,
        AssignmentStatus,
        Event,
        EventStatus,
        Mobilizer,
    )

    outside = Mobilizer(
        campaign_id=world.campaign.id,
        ward_id=world.other_ward.id,
        full_name="Out Side",
        phone="0711000111",
    )
    event = Event(
        campaign_id=world.campaign.id,
        ward_id=world.ward.id,
        title="Rally",
        status=EventStatus.DONE,
        scheduled_date=datetime(2027, 1, 1, tzinfo=UTC),
    )
    session.add_all([outside, event])
    await session.flush()
    outside_work = Assignment(
        campaign_id=world.campaign.id,
        mobilizer_id=outside.id,
        kind=AssignmentKind.WARD_WORK,
        ward_id=world.other_ward.id,
        amount_kes=500,
        status=AssignmentStatus.DONE,
    )
    session.add(outside_work)
    await session.commit()
    campaign, ward = str(world.campaign.id), str(world.ward.id)
    if route == "payment":
        answer = await client.post(
            "/api/payments/", headers=everyone[CO], json={"assignment": str(outside_work.id)}
        )
        assert (answer.status_code, answer.json()["detail"]) == (403, "That is outside your area.")
        return
    path, body = {
        "event": ("/api/events/", {"ward": ward, "title": "Walk"}),
        "supporter": (
            "/api/supporters/",
            {
                "ward": ward,
                "full_name": "Otieno K.",
                "phone": "+254700555666",
                "consent_given": True,
            },
        ),
    }[route]

    answer = await client.post(
        path,
        headers=everyone[CO],
        json={**body, "campaign": campaign, "mobilizer": str(outside.id)},
    )

    assert (answer.status_code, answer.json()["detail"]) == (403, "That is outside your area.")
