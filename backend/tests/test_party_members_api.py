"""The member routes: closed to campaign logins, open to a membership officer."""

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    PartyConsentChannel,
    PartyMember,
    PartyMemberStatus,
    PartyRole,
    PartyRoleName,
)
from backend.services import audit
from tests.conftest import World
from tests.factories import auth, make_user, sign_in


async def _pending(session: AsyncSession, world: World) -> PartyMember:
    member = PartyMember(
        full_name="Wanjiru Kamau",
        phone="+254712345678",
        ward_id=world.ward.id,
        status=PartyMemberStatus.PENDING,
        consent_channel=PartyConsentChannel.WEB_FORM,
        consent_wording="I agree.",
        consent_at=datetime.now(UTC),
    )
    session.add(member)
    await session.commit()
    return member


@pytest.mark.parametrize("role", ["candidate", "manager", "mobilizer"])
async def test_a_campaign_login_gets_403_on_every_member_route(
    client: httpx.AsyncClient, world: World, role: str
):
    headers = world.headers(role)
    someone = uuid.uuid4()
    calls = [
        client.get("/api/party/members/", headers=headers),
        client.get(f"/api/party/members/{someone}/", headers=headers),
        client.post(
            f"/api/party/members/{someone}/status/", json={"status": "approved"}, headers=headers
        ),
        client.get("/api/party/members/export.csv", headers=headers),
    ]
    assert [(await call).status_code for call in calls] == [403] * 4


async def test_an_officer_approves_a_pending_member_and_it_is_audited(
    client: httpx.AsyncClient, session: AsyncSession, world: World
):
    member = await _pending(session, world)
    officer = await make_user(session, username="ofisa", role=None)
    session.add(PartyRole(user_id=officer.id, role=PartyRoleName.MEMBERSHIP_OFFICER))
    await session.commit()
    headers = auth(await sign_in(client, "ofisa"))

    moved = await client.post(
        f"/api/party/members/{member.id}/status/", json={"status": "approved"}, headers=headers
    )

    assert moved.status_code == 200
    assert moved.json()["status"] == "approved"
    assert moved.json()["ward"]["id"] == str(world.ward.id)
    events = await audit.events(session, subject_id=member.id)
    assert [(e.action, e.detail) for e in events] == [
        ("member.status", {"from": "pending", "to": "approved"})
    ]
