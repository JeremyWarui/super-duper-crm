"""The volunteer routes: closed to campaign logins, open to a membership officer."""

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    ContactMethod,
    PartyConsentChannel,
    PartyMember,
    PartyMemberStatus,
    PartyRole,
    PartyRoleName,
    VolunteerProfile,
)
from backend.services import audit
from backend.services.consent import VOLUNTEER_WORDING
from tests.conftest import World
from tests.factories import auth, make_user, sign_in


@pytest.mark.parametrize("role", ["candidate", "manager", "mobilizer"])
async def test_a_campaign_login_gets_403_on_every_volunteer_route(
    client: httpx.AsyncClient, world: World, role: str
):
    headers = world.headers(role)
    someone = uuid.uuid4()
    calls = [
        client.get("/api/party/volunteers/", headers=headers),
        client.patch(
            f"/api/party/volunteers/{someone}/", json={"status": "active"}, headers=headers
        ),
        client.get("/api/party/volunteers/export.csv", headers=headers),
    ]
    assert [(await call).status_code for call in calls] == [403] * 3


async def test_an_officer_activates_an_approved_members_volunteer_and_it_is_audited(
    client: httpx.AsyncClient, session: AsyncSession, world: World
):
    member = PartyMember(
        full_name="Wanjiru Kamau",
        phone="+254712345678",
        ward_id=world.ward.id,
        status=PartyMemberStatus.APPROVED,
        consent_channel=PartyConsentChannel.WEB_FORM,
        consent_wording="I agree.",
        consent_at=datetime.now(UTC),
    )
    session.add(member)
    await session.flush()
    profile = VolunteerProfile(
        member_id=member.id,
        interests=["events"],
        preferred_contact=ContactMethod.CALL,
        consent_wording=VOLUNTEER_WORDING,
        consent_at=datetime.now(UTC),
    )
    session.add(profile)
    officer = await make_user(session, username="ofisa", role=None)
    session.add(PartyRole(user_id=officer.id, role=PartyRoleName.MEMBERSHIP_OFFICER))
    await session.commit()
    headers = auth(await sign_in(client, "ofisa"))

    moved = await client.patch(
        f"/api/party/volunteers/{profile.id}/", json={"status": "active"}, headers=headers
    )

    assert moved.status_code == 200
    assert moved.json()["status"] == "active"
    assert moved.json()["member_status"] == "approved"
    events = await audit.events(session, subject_id=profile.id)
    assert [(e.action, e.detail) for e in events] == [
        ("volunteer.status", {"from": "interested", "to": "active"})
    ]
