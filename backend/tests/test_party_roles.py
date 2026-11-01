"""Party roles: the guard lets an officer through and keeps campaigns out of reach."""

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import require_party_role
from backend.models import PartyRole, PartyRoleName, User, UserKind, UserRole
from backend.services import audit
from tests.conftest import World
from tests.factories import auth, make_officer, make_user, sign_in

OFFICER = PartyRoleName.MEMBERSHIP_OFFICER


async def test_an_officer_passes_the_guard_and_sees_no_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
):
    officer = await make_officer(session, world.ward, OFFICER)
    headers = auth(await sign_in(client, "ofisa"))

    me = (await client.get("/api/auth/me/", headers=headers)).json()
    assert me["party_roles"] == ["membership_officer"]
    assert (await client.get("/api/campaigns/", headers=headers)).json() == []

    officer = await session.get(type(officer), officer.id, populate_existing=True)
    await session.refresh(officer, ["party_roles"])
    assert await require_party_role(OFFICER)(officer, session) is officer


async def test_a_candidate_gets_403_from_the_guard(session: AsyncSession, world: World):
    await session.refresh(world.candidate, ["party_roles"])
    with pytest.raises(HTTPException) as refused:
        await require_party_role(OFFICER)(world.candidate, session)
    assert refused.value.status_code == 403


async def test_a_manager_login_cannot_be_given_a_party_role(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    admin_headers: dict[str, str],
):
    url = f"/api/admin/users/{world.manager.id}/party-roles/"
    refused = await client.post(url, json={"role": "membership_officer"}, headers=admin_headers)
    assert refused.status_code == 400

    staff = await make_user(session, username="staff", role=None)
    url = f"/api/admin/users/{staff.id}/party-roles/"
    unlinked = await client.post(url, json={"role": "membership_officer"}, headers=admin_headers)
    member_id = (await make_officer(session, world.ward, username="kin")).party_member_id
    await client.put(
        f"/api/admin/users/{staff.id}/party-member/",
        json={"member": str(member_id)},
        headers=admin_headers,
    )
    granted = await client.post(url, json={"role": "membership_officer"}, headers=admin_headers)
    assert unlinked.status_code == 400
    assert granted.status_code == 201
    assert granted.json()["party_roles"] == ["membership_officer"]
    actions = [event.action for event in await audit.events(session, subject_id=staff.id)]
    assert set(actions) == {"user.party_member", "party_role.grant"}


async def test_the_database_refuses_a_party_office_on_a_campaign_login(
    session: AsyncSession, world: World
):
    session.add(PartyRole(user_id=world.manager.id, role=OFFICER))

    with pytest.raises(IntegrityError):
        await session.commit()


async def test_the_database_refuses_a_campaign_role_on_an_officer_login(
    session: AsyncSession, world: World
):
    officer = await make_officer(session, world.ward, OFFICER)

    with pytest.raises(IntegrityError):
        await session.execute(
            update(User)
            .where(User.id == officer.id)
            .values(role=UserRole.MANAGER, kind=UserKind.CAMPAIGN)
        )
