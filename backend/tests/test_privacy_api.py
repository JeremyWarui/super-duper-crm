"""Erasure on request, data requests, withdrawal links for every supporter, closing a campaign."""

import uuid
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    AuditEvent,
    ContactMethod,
    FieldRole,
    Mobilizer,
    PartyMember,
    PartyMemberStatus,
    RegistrationStatus,
    SmsLog,
    Supporter,
    SupportLevel,
    TeamRegistration,
    VolunteerProfile,
    VolunteerStatus,
)
from backend.models.enums import PartyConsentChannel, PartyRoleName
from tests.conftest import World
from tests.factories import auth, make_officer, sign_in

PHONE = "+254711000111"


async def _people(session: AsyncSession, world: World) -> tuple:
    supporter = Supporter(
        campaign_id=world.campaign.id,
        ward_id=world.ward.id,
        mobilizer_id=world.mobilizer.id,
        full_name="Wanjiru Kamau",
        phone=PHONE,
        support_level=SupportLevel.SUPPORTER,
        withdraw_code="code-wanjiru",
    )
    volunteer = VolunteerProfile(
        campaign_id=world.campaign.id,
        first_name="Otieno",
        last_name="Ouma",
        phone="+254711000222",
        email="otieno@example.com",
        ward_id=world.ward.id,
        status=VolunteerStatus.WITHDRAWN,
        availability_notes="Weekends",
        preferred_contact=ContactMethod.SMS,
        consent_wording="I agree.",
        consent_at=datetime.now(UTC),
    )
    registration = TeamRegistration(
        campaign_id=world.campaign.id,
        role=FieldRole.AGENT,
        first_name="Akinyi",
        last_name="Odhiambo",
        phone="+254711000333",
        email="akinyi@example.com",
        id_number="12345678",
        ward_id=world.ward.id,
        consent_wording="I agree.",
        consent_version="1",
        status=RegistrationStatus.REJECTED,
        reason="Lives elsewhere",
    )
    session.add_all([supporter, volunteer, registration])
    session.add(
        Mobilizer(
            campaign_id=world.campaign.id,
            ward_id=world.other_ward.id,
            full_name="Akinyi Odhiambo",
            phone="+254711000333",
        )
    )
    session.add(
        SmsLog(
            campaign_id=world.campaign.id,
            purpose="invite",
            phone=PHONE,
            body="Hi",
            provider="console",
            status="practice",
        )
    )
    await session.commit()
    return supporter, volunteer, registration


async def test_erasure_blanks_every_personal_field_keeps_the_totals_and_audits_no_personal_data(
    session: AsyncSession, client: httpx.AsyncClient, world: World
) -> None:
    supporter, volunteer, registration = await _people(session, world)
    head = world.headers("manager")
    base = f"/api/campaigns/{world.campaign.id}/data"

    for path in (
        f"/supporters/{supporter.id}/erase/",
        f"/volunteers/{volunteer.id}/erase/",
        f"/registrations/{registration.id}/erase/",
    ):
        assert (await client.post(base + path, headers=head)).status_code == 204
    again = await client.post(base + f"/supporters/{supporter.id}/erase/", headers=head)
    for row in (supporter, volunteer, registration):
        await session.refresh(row)
    events = (
        await session.scalars(select(AuditEvent).where(AuditEvent.action.like("%.erase")))
    ).all()
    listed = (await client.get("/api/supporters/", headers=head)).json()

    assert again.status_code == 400
    assert (supporter.full_name, supporter.phone, supporter.withdraw_code) == ("Erased", "", None)
    assert (supporter.ward_id, supporter.mobilizer_id, supporter.support_level) == (
        world.ward.id,
        world.mobilizer.id,
        SupportLevel.SUPPORTER,
    )
    assert volunteer.first_name == "Erased" and volunteer.email is None
    assert volunteer.availability_notes is None and PHONE not in volunteer.phone
    assert registration.id_number != "12345678" and registration.email == ""
    assert (registration.first_name, registration.reason) == ("Erased", "")
    left = await session.scalar(select(Mobilizer).where(Mobilizer.user_id.is_(None)))
    await session.refresh(left)
    assert (left.full_name, left.phone) == ("Erased", "")
    assert [s["phone"] for s in listed] == [""] and len(listed) == 1
    assert await session.scalar(select(SmsLog.phone)) == ""
    assert len(events) == 3
    personal = ("Wanjiru", "Otieno", "Akinyi", "0001", "12345678", "example.com")
    for event in events:
        text = repr((event.detail, event.subject_type, event.actor_name))
        assert not any(bit in text for bit in personal)


async def test_only_a_withdrawn_volunteer_is_erased_and_a_coordinator_erases_nobody(
    session: AsyncSession, client: httpx.AsyncClient, world: World
) -> None:
    _, volunteer, _ = await _people(session, world)
    volunteer.status = VolunteerStatus.ACTIVE
    await session.commit()
    url = f"/api/campaigns/{world.campaign.id}/data/volunteers/{volunteer.id}/erase/"

    active = await client.post(url, headers=world.headers("manager"))
    mobilizer = await client.post(url, headers=world.headers("mobilizer"))

    assert active.status_code == 400
    assert mobilizer.status_code == 403


async def test_a_hand_registered_supporter_is_texted_a_working_withdrawal_link(
    session: AsyncSession, client: httpx.AsyncClient, world: World
) -> None:
    made = await client.post(
        "/api/supporters/",
        headers=world.headers("mobilizer"),
        json={
            "campaign": str(world.campaign.id),
            "full_name": "Baraka Mwangi",
            "phone": "0711000444",
            "consent_given": True,
        },
    )
    supporter = await session.get(Supporter, uuid.UUID(made.json()["id"]))
    text = await session.scalar(select(SmsLog).where(SmsLog.purpose == "withdrawal_link"))
    link = await client.get(
        f"/api/campaigns/{world.campaign.id}/data/supporters/{supporter.id}/withdrawal/",
        headers=world.headers("candidate"),
    )
    gone = await client.post(f"/api/join/withdraw/{supporter.withdraw_code}/")
    session.expunge_all()

    assert made.status_code == 201
    assert supporter.withdraw_code in text.body and text.phone == "+254711000444"
    assert link.json()["url"].endswith(f"/withdraw/{supporter.withdraw_code}")
    assert gone.status_code == 200
    assert await session.get(Supporter, supporter.id) is None


async def test_closing_a_campaign_makes_it_read_only_for_every_role(
    client: httpx.AsyncClient, world: World
) -> None:
    base = f"/api/campaigns/{world.campaign.id}/data"
    by_manager = await client.post(base + "/close/", headers=world.headers("manager"))
    closed = await client.post(base + "/close/", headers=world.headers("candidate"))

    write = await client.post(
        "/api/supporters/",
        headers=world.headers("mobilizer"),
        json={"campaign": str(world.campaign.id), "full_name": "Late", "consent_given": True},
    )
    read = await client.get("/api/supporters/", headers=world.headers("manager"))
    request = await client.post(
        base + "/requests/",
        headers=world.headers("manager"),
        json={"kind": "access", "requester_name": "Late", "requester_contact": "0711"},
    )

    assert by_manager.status_code == 403
    assert closed.status_code == 200 and closed.json()["closed_at"]
    assert write.status_code == 403 and "read-only" in write.json()["detail"]
    assert read.status_code == 200
    assert request.status_code == 201


async def test_supporters_are_erased_only_by_the_explicit_action_after_the_retention_period(
    session: AsyncSession, client: httpx.AsyncClient, world: World
) -> None:
    supporter, _, _ = await _people(session, world)
    base = f"/api/campaigns/{world.campaign.id}/data"
    head = world.headers("candidate")

    open_campaign = await client.post(base + "/erase-supporters/", headers=head)
    await client.post(base + "/close/", headers=head)
    too_soon = await client.post(base + "/erase-supporters/", headers=head)
    await session.refresh(supporter)
    kept = supporter.full_name
    world.campaign.closed_at = datetime.now(UTC) - timedelta(days=200)
    await session.commit()
    done = await client.post(base + "/erase-supporters/", headers=head)
    await session.refresh(supporter)

    assert open_campaign.status_code == 400
    assert too_soon.status_code == 400 and "kept until" in too_soon.json()["detail"]
    assert kept == "Wanjiru Kamau"
    assert done.json() == {"erased": 1}
    assert supporter.full_name == "Erased" and supporter.ward_id == world.ward.id


@pytest.mark.party_only
async def test_a_data_request_is_due_by_law_and_each_scope_sees_only_its_own(
    session: AsyncSession, client: httpx.AsyncClient, world: World
) -> None:
    officer = await make_officer(session, world.ward, PartyRoleName.MEMBERSHIP_OFFICER)
    party_head = auth(await sign_in(client, officer.username))
    asked = {"requester_name": "Mary", "requester_contact": "0711", "received_on": "2026-11-02"}

    access = await client.post(
        f"/api/campaigns/{world.campaign.id}/data/requests/",
        headers=world.headers("manager"),
        json={"kind": "access", **asked},
    )
    erasure = await client.post(
        "/api/party/data-requests/", headers=party_head, json={"kind": "erasure", **asked}
    )
    bare = await client.patch(
        f"/api/party/data-requests/{erasure.json()['id']}/",
        headers=party_head,
        json={"status": "done"},
    )
    party_list = (await client.get("/api/party/data-requests/", headers=party_head)).json()
    workspace_list = (
        await client.get(
            f"/api/campaigns/{world.campaign.id}/data/requests/", headers=world.headers("manager")
        )
    ).json()

    assert access.json()["due_on"] == str(date(2026, 11, 9))
    assert erasure.json()["due_on"] == str(date(2026, 11, 16))
    assert bare.status_code == 400
    assert [r["kind"] for r in party_list] == ["erasure"]
    assert [r["kind"] for r in workspace_list] == ["access"]


@pytest.mark.party_only
async def test_a_withdrawn_party_member_is_erased_and_an_approved_one_is_not(
    session: AsyncSession, client: httpx.AsyncClient, world: World, organisation_type
) -> None:
    officer = await make_officer(session, world.ward, PartyRoleName.MEMBERSHIP_OFFICER)
    head = auth(await sign_in(client, officer.username))
    member = PartyMember(
        full_name="Grace Wambui",
        phone="+254711000555",
        email="grace@example.com",
        ward_id=world.ward.id,
        status=PartyMemberStatus.APPROVED,
        consent_wording="I agree.",
        consent_channel=PartyConsentChannel.OFFICER_ENTRY,
        consent_at=datetime.now(UTC),
    )
    session.add(member)
    await session.commit()

    approved = await client.post(f"/api/party/members/{member.id}/erase/", headers=head)
    member.status = PartyMemberStatus.WITHDRAWN
    await session.commit()
    erased = await client.post(f"/api/party/members/{member.id}/erase/", headers=head)
    await session.refresh(member)

    assert approved.status_code == 400
    assert erased.status_code == 200 and erased.json()["phone"] == ""
    assert (member.full_name, member.email) == ("Erased", None)
    assert "555" not in member.phone and member.erased_at is not None
