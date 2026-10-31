"""Nominations: who can be nominated, the move table, and aspirants following their member."""

import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Aspirant,
    AspirantStatus,
    PartyConsentChannel,
    PartyMember,
    PartyMemberStatus,
    PartyRoleName,
)
from backend.services import membership
from backend.services.consent import PARTY_WORDING
from tests.conftest import World
from tests.factories import auth, make_officer, sign_in

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
