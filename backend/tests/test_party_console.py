"""The party console's top bar: search sees only the caller's registers, and the counts are true."""

from datetime import UTC, datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Aspirant,
    AspirantStatus,
    PartyConsentChannel,
    PartyMember,
    PartyMemberStatus,
    PartyRoleName,
    Seat,
)
from backend.services.consent import PARTY_WORDING
from tests.conftest import World
from tests.factories import auth, make_officer, sign_in


async def _member(
    session: AsyncSession, world: World, name: str, phone: str, status
) -> PartyMember:
    member = PartyMember(
        full_name=name,
        phone=phone,
        ward_id=world.ward.id,
        status=status,
        consent_wording=PARTY_WORDING[PartyConsentChannel.OFFICER_ENTRY],
        consent_channel=PartyConsentChannel.OFFICER_ENTRY,
        consent_at=datetime.now(UTC),
    )
    session.add(member)
    await session.commit()
    return member


async def _officer(client, session, world: World, role: PartyRoleName, username: str) -> dict:
    await make_officer(session, world.ward, role, username=username)
    return auth(await sign_in(client, username))


async def test_search_returns_only_what_the_caller_s_offices_may_see(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    nominee = await _member(
        session, world, "Achieng Otieno", "+254711000001", PartyMemberStatus.APPROVED
    )
    await _member(session, world, "Achieng Wanjiru", "+254711000002", PartyMemberStatus.PENDING)
    session.add(
        Aspirant(
            member_id=nominee.id,
            seat=Seat.MCA,
            ward_id=world.ward.id,
            status=AspirantStatus.SUBMITTED,
        )
    )
    await session.commit()
    membership = await _officer(client, session, world, PartyRoleName.MEMBERSHIP_OFFICER, "usajili")
    nominations = await _officer(
        client, session, world, PartyRoleName.NOMINATIONS_OFFICER, "uteuzi"
    )
    finance = await _officer(client, session, world, PartyRoleName.FINANCE_OFFICER, "pesa")

    async def hits(headers: dict) -> list[tuple[str, str]]:
        answer = await client.get("/api/party/search/?q=achieng", headers=headers)
        assert answer.status_code == 200, answer.text
        return [(h["kind"], h["label"]) for h in answer.json()]

    manager = await client.get("/api/party/search/?q=achieng", headers=world.headers("manager"))

    assert await hits(membership) == [
        ("member", "Achieng Otieno"),
        ("member", "Achieng Wanjiru"),
    ]
    assert await hits(nominations) == [("aspirant", "Achieng Otieno")]
    assert await hits(finance) == []
    assert manager.status_code == 403


async def test_the_membership_officer_s_count_matches_pending_applications(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    for n in range(3):
        await _member(
            session, world, f"Applicant {n}", f"+25472200000{n}", PartyMemberStatus.PENDING
        )
    await _member(session, world, "Already in", "+254722000009", PartyMemberStatus.APPROVED)
    membership = await _officer(client, session, world, PartyRoleName.MEMBERSHIP_OFFICER, "usajili")

    answer = (await client.get("/api/party/notifications/", headers=membership)).json()

    assert answer == [{"key": "pending_members", "count": 3}]
