"""Nominations: who can be nominated, the move table, and aspirants following their member."""

import asyncio
import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from backend.models import (
    Aspirant,
    AspirantStatus,
    Campaign,
    PartyConsentChannel,
    PartyMember,
    PartyMemberStatus,
    PartyRoleName,
    Seat,
    User,
    UserRole,
)
from backend.services import aspirants, membership
from backend.services.consent import PARTY_WORDING
from backend.services.errors import Refused
from tests.conftest import POSTGRES, World
from tests.factories import auth, make_officer, sign_in

pytestmark = pytest.mark.party_only

PHONE = "+254711222333"


async def _member(session: AsyncSession, world: World, status: PartyMemberStatus) -> PartyMember:
    member = PartyMember(
        full_name="Wanjiru Kamau",
        phone=PHONE,
        ward_id=world.ward.id,
        status=status,
        consent_wording=PARTY_WORDING[PartyConsentChannel.OFFICER_ENTRY],
        consent_channel=PartyConsentChannel.OFFICER_ENTRY,
        consent_at=datetime.now(UTC),
        withdraw_code="member-code",
    )
    session.add(member)
    await session.commit()
    return member


async def _nominations_officer(client: httpx.AsyncClient, session, world: World) -> dict:
    await make_officer(session, world.ward, PartyRoleName.NOMINATIONS_OFFICER, username="teuzi")
    return auth(await sign_in(client, "teuzi"))


def _mca(member: PartyMember, world: World) -> dict:
    return {"member": str(member.id), "seat": "mca", "ward": str(world.ward.id)}


async def _approved_aspirant(client, session, world, headers) -> tuple[PartyMember, str]:
    member = await _member(session, world, PartyMemberStatus.APPROVED)
    created = await client.post("/api/party/aspirants/", json=_mca(member, world), headers=headers)
    url = f"/api/party/aspirants/{created.json()['id']}/status/"
    for step in ("submitted", "approved"):
        assert (await client.post(url, json={"status": step}, headers=headers)).status_code == 200
    return member, created.json()["id"]


async def test_only_an_approved_member_is_nominated(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    headers = await _nominations_officer(client, session, world)
    member = await _member(session, world, PartyMemberStatus.PENDING)

    refused = await client.post("/api/party/aspirants/", json=_mca(member, world), headers=headers)
    member.status = PartyMemberStatus.APPROVED
    await session.commit()
    created = await client.post("/api/party/aspirants/", json=_mca(member, world), headers=headers)

    assert refused.status_code == 400
    assert created.status_code == 201
    assert (created.json()["status"], created.json()["area"]["name"]) == ("draft", world.ward.name)


async def test_approval_is_refused_while_the_member_is_suspended(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    headers = await _nominations_officer(client, session, world)
    member = await _member(session, world, PartyMemberStatus.APPROVED)
    created = await client.post("/api/party/aspirants/", json=_mca(member, world), headers=headers)
    url = f"/api/party/aspirants/{created.json()['id']}/status/"
    await client.post(url, json={"status": "submitted"}, headers=headers)
    member.status = PartyMemberStatus.SUSPENDED
    await session.commit()

    refused = await client.post(url, json={"status": "approved"}, headers=headers)

    assert refused.status_code == 400
    aspirant = await session.get(Aspirant, uuid.UUID(created.json()["id"]), populate_existing=True)
    assert aspirant.status is AspirantStatus.SUBMITTED


async def test_suspending_the_member_suspends_their_approved_aspirant(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    headers = await _nominations_officer(client, session, world)
    member, aspirant_id = await _approved_aspirant(client, session, world, headers)
    officer = await make_officer(session, world.ward, PartyRoleName.MEMBERSHIP_OFFICER)

    await membership.move(session, member, PartyMemberStatus.SUSPENDED, actor=officer)
    await session.commit()

    read = await client.get(f"/api/party/aspirants/{aspirant_id}/", headers=headers)
    assert read.json()["status"] == "suspended"


async def test_the_members_public_withdrawal_withdraws_their_aspirant(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    headers = await _nominations_officer(client, session, world)
    _, aspirant_id = await _approved_aspirant(client, session, world, headers)

    await client.post("/api/party/withdraw/member-code/")
    read = await client.get(f"/api/party/aspirants/{aspirant_id}/", headers=headers)

    assert read.json()["status"] == "withdrawn"


async def test_a_membership_officer_cannot_read_nominations(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await make_officer(session, world.ward, PartyRoleName.MEMBERSHIP_OFFICER)
    headers = auth(await sign_in(client, "ofisa"))

    assert (await client.get("/api/party/aspirants/", headers=headers)).status_code == 403


async def test_the_candidate_search_needs_the_whole_phone_and_never_shows_it(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    headers = await _nominations_officer(client, session, world)
    member = await _member(session, world, PartyMemberStatus.APPROVED)
    url = "/api/party/aspirants/candidates/"

    prefix = await client.get(url, params={"q": PHONE[:9]}, headers=headers)
    whole = await client.get(url, params={"q": PHONE}, headers=headers)

    assert prefix.json() == []
    assert [row["id"] for row in whole.json()] == [str(member.id)]
    assert "phone" not in whole.json()[0]
    assert (await session.scalars(select(Aspirant))).all() == []


def _workspace(username: str = "wanjiru") -> dict:
    return {"candidate": {"username": username}, "manager": {"username": f"{username}-mgr"}}


async def test_the_workspace_takes_the_aspirants_seat_and_area_and_links_the_login(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    headers = await _nominations_officer(client, session, world)
    member, aspirant_id = await _approved_aspirant(client, session, world, headers)

    made = await client.post(
        f"/api/party/aspirants/{aspirant_id}/workspace/", json=_workspace(), headers=headers
    )

    assert made.status_code == 201
    campaign = await session.get(Campaign, uuid.UUID(made.json()["aspirant"]["campaign_id"]))
    assert (campaign.seat, campaign.ward_id) == (Seat.MCA, world.ward.id)
    login = await session.scalar(select(User).where(User.username == "wanjiru"))
    assert (login.role, login.party_member_id) == (UserRole.CANDIDATE, member.id)
    assert all(row["invite"] in ("email", "none") for row in made.json()["logins"])


async def test_a_second_workspace_is_refused_and_leaves_nothing_behind(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    headers = await _nominations_officer(client, session, world)
    _, aspirant_id = await _approved_aspirant(client, session, world, headers)
    url = f"/api/party/aspirants/{aspirant_id}/workspace/"
    await client.post(url, json=_workspace(), headers=headers)
    campaigns = await session.scalar(select(func.count()).select_from(Campaign))

    again = await client.post(url, json=_workspace("other"), headers=headers)

    assert again.status_code == 400
    assert await session.scalar(select(func.count()).select_from(Campaign)) == campaigns
    assert await session.scalar(select(User).where(User.username == "other")) is None


async def test_deleting_the_campaign_keeps_the_aspirant_approved_without_one(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    headers = await _nominations_officer(client, session, world)
    member, aspirant_id = await _approved_aspirant(client, session, world, headers)
    url = f"/api/party/aspirants/{aspirant_id}/workspace/"
    made = await client.post(url, json=_workspace(), headers=headers)
    campaign_id = made.json()["aspirant"]["campaign_id"]

    gone = await client.delete(f"/api/admin/campaigns/{campaign_id}/", headers=admin_headers)

    read = (await client.get(f"/api/party/aspirants/{aspirant_id}/", headers=headers)).json()
    assert gone.status_code in (200, 204)
    assert (read["status"], read["campaign_id"]) == ("approved", None)
    assert await session.get(PartyMember, member.id, populate_existing=True) is not None


@pytest.mark.skipif(not POSTGRES, reason="row locks need TEST_POSTGRES=1")
async def test_two_officers_at_once_make_one_workspace(
    engine: AsyncEngine, client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    headers = await _nominations_officer(client, session, world)
    _, aspirant_id = await _approved_aspirant(client, session, world, headers)
    officer = await session.scalar(select(User).where(User.username == "teuzi"))

    async def attempt(username: str) -> bool:
        async with AsyncSession(engine, expire_on_commit=False) as own:
            aspirant = await aspirants.get_aspirant(own, uuid.UUID(aspirant_id))
            try:
                await aspirants.create_workspace(
                    own, aspirant, actor=officer, candidate={"username": username}
                )
            except Refused:
                return False
            return True

    made = await asyncio.gather(attempt("first"), attempt("second"))

    assert sorted(made) == [False, True]
    assert await session.scalar(select(func.count()).select_from(Campaign)) == 2
    logins = await session.scalars(
        select(User.username).where(User.username.in_(["first", "second"]))
    )
    assert len(logins.all()) == 1


async def test_the_candidate_search_refuses_hidden_characters(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    headers = await _nominations_officer(client, session, world)

    refused = await client.get(
        "/api/party/aspirants/candidates/", params={"q": "ab\x00cd"}, headers=headers
    )

    assert refused.status_code == 400


async def test_a_workspace_refuses_a_blank_title_and_a_hidden_character_in_a_name(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    headers = await _nominations_officer(client, session, world)
    _, aspirant_id = await _approved_aspirant(client, session, world, headers)
    url = f"/api/party/aspirants/{aspirant_id}/workspace/"

    blank = await client.post(url, json={**_workspace(), "title": "   "}, headers=headers)
    hidden = await client.post(
        url, json={"candidate": {"username": "wanjiru", "first_name": "Wa\x00"}}, headers=headers
    )

    assert (blank.status_code, hidden.status_code) == (400, 400)
    assert await session.scalar(select(func.count()).select_from(Campaign)) == 1


async def test_a_nomination_moved_by_its_member_drops_the_officers_reason(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    headers = await _nominations_officer(client, session, world)
    member = await _member(session, world, PartyMemberStatus.APPROVED)
    created = await client.post("/api/party/aspirants/", json=_mca(member, world), headers=headers)
    url = f"/api/party/aspirants/{created.json()['id']}/status/"
    await client.post(url, json={"status": "submitted"}, headers=headers)
    await client.post(url, json={"status": "approved", "reason": "Strong"}, headers=headers)
    officer = await make_officer(session, world.ward, PartyRoleName.MEMBERSHIP_OFFICER)

    await membership.move(session, member, PartyMemberStatus.SUSPENDED, actor=officer)
    await session.commit()

    read = await client.get(f"/api/party/aspirants/{created.json()['id']}/", headers=headers)
    assert (read.json()["status"], read.json()["status_reason"]) == ("suspended", None)
