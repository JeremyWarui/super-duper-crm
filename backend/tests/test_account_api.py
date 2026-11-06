"""Email sign-in, member logins made from joins, and the member's own account."""

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.routing import APIRoute, iter_route_contexts
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_current_user
from backend.api.install import InstallationRoute
from backend.main import app
from backend.models import (
    OrganisationType,
    PartyMember,
    PartyMemberStatus,
    PartyRequest,
    User,
    UserKind,
    UserRole,
    VolunteerProfile,
    VolunteerStatus,
)
from backend.services.membership import process_requests
from tests.conftest import World
from tests.factories import TEST_PASSWORD, auth, fresh_password, make_user

pytestmark = pytest.mark.party_only

APPLICANT = "wanjiru@example.com"
LOGIN = "/api/auth/login/"


def _application(world: World, **overrides) -> dict:
    return {
        "first_name": "Wanjiru",
        "surname": "Kamau",
        "phone": "0712 345678",
        "email": "Wanjiru@Example.com",
        "password": TEST_PASSWORD,
        "ward": str(world.centre.ward_id),
        "registration_centre": str(world.centre.id),
        "consent_given": True,
        **overrides,
    }


async def _joined(client: httpx.AsyncClient, session: AsyncSession, world: World, **overrides):
    """An applicant applied, and their join taken from the inbox."""
    await client.post("/api/party/join/", json=_application(world, **overrides))
    await process_requests(session)
    return await session.scalar(select(PartyMember).where(PartyMember.phone == "+254712345678"))


async def _approved_member_token(
    client: httpx.AsyncClient, session: AsyncSession, world: World, **overrides
) -> tuple[PartyMember, str]:
    member = await _joined(client, session, world, **overrides)
    member.status = PartyMemberStatus.APPROVED
    await session.commit()
    signed_in = await client.post(LOGIN, json={"email": APPLICANT, "password": TEST_PASSWORD})
    assert signed_in.status_code == 200, signed_in.text
    return member, signed_in.json()["token"]


async def test_a_login_signs_in_with_its_email_in_any_case_and_no_longer_with_its_username(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await make_user(session, username="amina", role=UserRole.MANAGER)

    by_email = await client.post(
        LOGIN, json={"email": " AMINA@example.test ", "password": TEST_PASSWORD}
    )
    by_name = await client.post(LOGIN, json={"username": "amina", "password": TEST_PASSWORD})
    name_as_email = await client.post(LOGIN, json={"email": "amina", "password": TEST_PASSWORD})

    assert (by_email.status_code, by_email.json()["user"]["kind"]) == (200, "campaign")
    assert (by_name.status_code, name_as_email.status_code) == (400, 400)


async def test_an_applied_join_makes_a_member_login_that_signs_in_only_once_approved(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    member = await _joined(client, session, world)
    login = await session.scalar(select(User).where(User.party_member_id == member.id))
    pending = await client.post(LOGIN, json={"email": APPLICANT, "password": TEST_PASSWORD})
    wrong = await client.post(LOGIN, json={"email": APPLICANT, "password": fresh_password()})

    member.status = PartyMemberStatus.APPROVED
    await session.commit()
    approved = await client.post(LOGIN, json={"email": APPLICANT, "password": TEST_PASSWORD})

    assert (login.kind, login.email, login.role) == (UserKind.MEMBER, APPLICANT, None)
    assert (pending.status_code, pending.json()) == (wrong.status_code, wrong.json())
    assert approved.json()["user"]["member_account"] is True


async def test_a_join_whose_email_another_login_holds_makes_no_member_login(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    await make_user(session, username="taken", role=UserRole.MANAGER, email=APPLICANT)

    member = await _joined(client, session, world)
    logins = (await session.scalars(select(User).where(User.party_member_id == member.id))).all()
    listed = (await client.get("/api/party/members/", headers=admin_headers)).json()["items"]

    assert logins == []
    assert [(m["full_name"], m["has_login"]) for m in listed] == [("Wanjiru Kamau", False)]


async def test_a_member_login_gets_403_from_every_staff_and_campaign_route(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    organisation_type: OrganisationType,
) -> None:
    _, token = await _approved_member_token(client, session, world)
    answers = {}
    for route in iter_route_contexts(app.routes):
        original = route.original_route
        if not isinstance(original, APIRoute) or not _guarded(route.dependant):
            continue
        if isinstance(original, InstallationRoute) and original.installation != organisation_type:
            continue
        path = route.path
        for name in route.param_convertors:
            path = path.replace("{" + name + "}", str(uuid.uuid4()))
        for method in route.methods:
            response = await client.request(method, path, headers=auth(token), json={})
            answers[(method, route.path)] = response.status_code

    assert answers and set(answers.values()) == {403}


def _guarded(dependant) -> bool:
    return any(d.call is get_current_user or _guarded(d) for d in dependant.dependencies)


async def test_a_suspended_member_is_signed_out_at_the_next_account_request(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    member, token = await _approved_member_token(client, session, world)
    before = await client.get("/api/account/", headers=auth(token))

    member.status = PartyMemberStatus.SUSPENDED
    await session.commit()
    after = await client.get("/api/account/", headers=auth(token))

    assert before.json()["phone"] == "07•• ••• 678"
    assert after.status_code == 401


async def test_a_linked_campaign_login_reads_its_members_account_and_others_get_403(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    member = await _joined(client, session, world, email="other@example.com")
    member.status = PartyMemberStatus.APPROVED
    world.candidate.party_member_id = member.id
    await session.commit()

    linked = await client.get("/api/account/", headers=world.headers("candidate"))
    unlinked = await client.get("/api/account/", headers=world.headers("manager"))

    assert (linked.json()["first_name"], unlinked.status_code) == ("Wanjiru", 403)


async def test_a_member_volunteers_changes_stops_and_stays_a_member(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    member, token = await _approved_member_token(client, session, world)
    part = {
        "profession": "farmer",
        "areas": ["materials"],
        "preferred_contact": "call",
        "consent_given": True,
    }

    joined = await client.put("/api/account/volunteer/", json=part, headers=auth(token))
    changed = await client.put(
        "/api/account/volunteer/",
        json={**part, "areas": ["recruiting", "other"], "area_other": "Drama"},
        headers=auth(token),
    )
    stopped = await client.post("/api/account/volunteer/stop/", headers=auth(token))
    profile = await session.scalar(
        select(VolunteerProfile).execution_options(populate_existing=True)
    )
    stopped_status, stopped_code = profile.status, profile.withdraw_code
    # An officer erases the withdrawn profile; volunteering again is fresh consent.
    profile.erased_at = datetime.now(UTC)
    await session.commit()
    again = await client.put("/api/account/volunteer/", json=part, headers=auth(token))
    profiles = (
        await session.scalars(select(VolunteerProfile).execution_options(populate_existing=True))
    ).all()
    await session.refresh(member)

    assert joined.json()["volunteer"]["status"] == "interested"
    assert changed.json()["volunteer"]["areas"] == ["recruiting", "other"]
    assert (stopped.status_code, stopped_status, stopped_code) == (
        200,
        VolunteerStatus.WITHDRAWN,
        None,
    )
    assert stopped.json()["volunteer"] is None
    assert (again.json()["volunteer"]["status"], len(profiles)) == ("interested", 1)
    assert profiles[0].erased_at is None
    assert member.status is PartyMemberStatus.APPROVED


async def test_leaving_the_party_queues_the_withdrawal_and_ends_the_session(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    member, token = await _approved_member_token(client, session, world)

    left = await client.post("/api/account/leave/", headers=auth(token))
    queued = (await session.scalars(select(PartyRequest))).all()
    after = await client.get("/api/account/", headers=auth(token))
    await process_requests(session)
    await session.refresh(member)

    assert (left.status_code, len(queued), after.status_code) == (204, 1, 401)
    assert member.status is PartyMemberStatus.WITHDRAWN


async def test_a_member_with_a_login_can_be_deleted_and_the_login_no_longer_signs_in(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    member, _ = await _approved_member_token(client, session, world)

    await session.delete(member)
    await session.commit()
    signed_in = await client.post(LOGIN, json={"email": APPLICANT, "password": TEST_PASSWORD})

    assert signed_in.status_code == 400
