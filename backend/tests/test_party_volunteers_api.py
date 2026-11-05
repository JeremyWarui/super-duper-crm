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
    PartyRoleName,
    VolunteerProfile,
    VolunteerStatus,
)
from backend.services import audit
from backend.services.consent import VOLUNTEER_WORDING
from tests.conftest import World
from tests.factories import auth, make_officer, sign_in

pytestmark = pytest.mark.party_only


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
        first_name="Wanjiru",
        last_name="Kamau",
        phone=member.phone,
        ward_id=member.ward_id,
        interests=["door_to_door"],
        preferred_contact=ContactMethod.CALL,
        consent_wording=VOLUNTEER_WORDING,
        consent_at=datetime.now(UTC),
    )
    session.add(profile)
    await make_officer(session, world.ward, PartyRoleName.MEMBERSHIP_OFFICER)
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


async def test_a_campaign_volunteer_stays_out_of_the_register_its_csv_and_the_dashboard(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
):
    session.add(
        VolunteerProfile(
            campaign_id=world.campaign.id,
            first_name="Otieno",
            last_name="Kamau",
            phone="+254733000111",
            ward_id=world.ward.id,
            status=VolunteerStatus.ACTIVE,
            interests=["door_to_door"],
            preferred_contact=ContactMethod.CALL,
            consent_wording=VOLUNTEER_WORDING,
            consent_at=datetime.now(UTC),
        )
    )
    await session.commit()

    register = (await client.get("/api/party/volunteers/", headers=admin_headers)).json()
    csv = (await client.get("/api/party/volunteers/export.csv", headers=admin_headers)).text
    board = (await client.get("/api/party/dashboard/", headers=admin_headers)).json()

    assert register["total"] == 0
    assert "Otieno" not in csv
    assert (board["active_volunteers"], board["volunteers_by_interest"]) == (0, [])
