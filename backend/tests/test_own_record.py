"""Officers act only while linked to an approved member, and never on their own records."""

from datetime import UTC, datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    ContactMethod,
    PartyMember,
    PartyMemberStatus,
    PartyRole,
    PartyRoleName,
    VolunteerProfile,
)
from backend.services.consent import VOLUNTEER_WORDING
from tests.conftest import World
from tests.factories import auth, make_officer, make_user, sign_in

BOTH = (PartyRoleName.MEMBERSHIP_OFFICER, PartyRoleName.NOMINATIONS_OFFICER)


async def test_an_officer_cannot_move_their_own_membership_volunteering_or_nomination(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    officer = await make_officer(session, world.ward, *BOTH)
    own = officer.party_member_id
    profile = VolunteerProfile(
        member_id=own,
        interests=["events"],
        preferred_contact=ContactMethod.CALL,
        consent_wording=VOLUNTEER_WORDING,
        consent_at=datetime.now(UTC),
    )
    session.add(profile)
    await session.commit()
    headers = auth(await sign_in(client, "ofisa"))

    # The member move goes last: if it landed it would also lock the officer out.
    volunteer = await client.patch(
        f"/api/party/volunteers/{profile.id}/", json={"status": "active"}, headers=headers
    )
    nomination = await client.post(
        "/api/party/aspirants/",
        json={"member": str(own), "seat": "mca", "ward": str(world.ward.id)},
        headers=headers,
    )
    member = await client.post(
        f"/api/party/members/{own}/status/", json={"status": "suspended"}, headers=headers
    )

    assert [volunteer.status_code, nomination.status_code, member.status_code] == [403] * 3
    assert (await session.get(PartyMember, own, populate_existing=True)).status is (
        PartyMemberStatus.APPROVED
    )


async def test_an_officer_works_only_while_linked_to_an_approved_member(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    officer = await make_officer(session, world.ward, PartyRoleName.MEMBERSHIP_OFFICER)
    headers = auth(await sign_in(client, "ofisa"))
    unlinked = await make_user(session, username="loose", role=None)
    session.add(PartyRole(user_id=unlinked.id, role=PartyRoleName.MEMBERSHIP_OFFICER))
    await session.commit()

    before = await client.get("/api/party/members/", headers=headers)
    member = await session.get(PartyMember, officer.party_member_id)
    member.status = PartyMemberStatus.SUSPENDED
    await session.commit()
    after = await client.get("/api/party/members/", headers=headers)
    loose = await client.get("/api/party/members/", headers=auth(await sign_in(client, "loose")))

    assert (before.status_code, after.status_code, loose.status_code) == (200, 403, 403)
