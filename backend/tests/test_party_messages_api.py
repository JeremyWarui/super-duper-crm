"""Party texts to members and volunteers: drafted by the Comms Officer, sent only once the Party
Super Admin approves, and only to people whose consent covers SMS."""

import json
import secrets
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Constituency,
    ContactMethod,
    PartyConsentChannel,
    PartyMember,
    PartyMemberStatus,
    PartyRoleName,
    Profession,
    SmsLog,
    VolunteerProfile,
    VolunteerStatus,
    Ward,
)
from backend.services.consent import MEMBER_SMS_WORDING, PARTY_WORDING, VOLUNTEER_WORDING
from tests.conftest import World
from tests.factories import auth, make_officer, sign_in

pytestmark = pytest.mark.party_only

RECORDED = json.loads((Path(__file__).parent / "fixtures" / "africastalking.json").read_text())
MESSAGES = "/api/party/messages/"
STOPPER = "+254712345678"


def _member(world: World, phone: str, sms: bool) -> PartyMember:
    now = datetime.now(UTC)
    return PartyMember(
        full_name=f"Member {phone[-3:]}",
        phone=phone,
        ward_id=world.ward.id,
        status=PartyMemberStatus.APPROVED,
        consent_wording=PARTY_WORDING[PartyConsentChannel.WEB_FORM],
        consent_channel=PartyConsentChannel.WEB_FORM,
        consent_at=now,
        sms_consent_wording=MEMBER_SMS_WORDING if sms else None,
        sms_consent_at=now if sms else None,
    )


def _volunteer(world: World, member: PartyMember, contact: ContactMethod) -> VolunteerProfile:
    phone = member.phone
    return VolunteerProfile(
        member_id=member.id,
        first_name="Vol",
        last_name=phone[-3:],
        phone=phone,
        ward_id=world.ward.id,
        profession=Profession.TEACHER,
        status=VolunteerStatus.ACTIVE,
        interests=["fundraising"],
        preferred_contact=contact,
        consent_wording=VOLUNTEER_WORDING,
        consent_at=datetime.now(UTC),
    )


@pytest.fixture
async def comms(session: AsyncSession, client: httpx.AsyncClient, world: World) -> dict:
    await make_officer(session, world.ward, PartyRoleName.COMMS_OFFICER, username="habari")
    return auth(await sign_in(client, "habari"))


@pytest.fixture
async def people(session: AsyncSession, world: World) -> None:
    by_sms, by_email = (_member(world, p, sms=False) for p in ("+254712000003", "+254712000004"))
    session.add_all(
        [
            _member(world, STOPPER, sms=True),
            _member(world, "+254712000002", sms=False),
            by_sms,
            by_email,
        ]
    )
    await session.flush()
    session.add_all(
        [
            _volunteer(world, by_sms, ContactMethod.SMS),
            _volunteer(world, by_email, ContactMethod.EMAIL),
        ]
    )
    await session.commit()


async def _draft(client, headers: dict, audience: str = "members") -> dict:
    drafted = await client.post(
        MESSAGES,
        json={"audience": audience, "body": "Branch meeting on Saturday."},
        headers=headers,
    )
    assert drafted.status_code == 201, drafted.text
    return drafted.json()


async def test_only_consenting_people_are_counted_and_sent_once_the_super_admin_approves(
    client: httpx.AsyncClient,
    session: AsyncSession,
    comms: dict,
    people: None,
    admin_headers: dict,
) -> None:
    members = await _draft(client, comms)
    volunteers = await _draft(client, comms, "volunteers")
    before = await session.scalar(select(SmsLog.id).limit(1))

    by_comms = await client.post(f"{MESSAGES}{members['id']}/send/", headers=comms)
    sent = await client.post(f"{MESSAGES}{members['id']}/send/", headers=admin_headers)
    again = await client.post(f"{MESSAGES}{members['id']}/send/", headers=admin_headers)
    await client.post(f"{MESSAGES}{volunteers['id']}/send/", headers=admin_headers)
    logged = (
        await session.execute(select(SmsLog.phone, SmsLog.purpose, SmsLog.party_message_id))
    ).all()

    assert (members["targeted"], volunteers["targeted"]) == (1, 1)
    assert before is None
    assert by_comms.status_code == 403
    assert (sent.json()["status"], sent.json()["recipients"]) == ("sent", 1)
    assert again.status_code == 400
    assert sorted(logged) == [
        ("+254712000003", "party", uuid.UUID(volunteers["id"])),
        (STOPPER, "party", uuid.UUID(members["id"])),
    ]


async def test_the_super_admin_cannot_approve_their_own_draft(
    client: httpx.AsyncClient, people: None, admin_headers: dict
) -> None:
    own = await _draft(client, admin_headers)

    refused = await client.post(f"{MESSAGES}{own['id']}/send/", headers=admin_headers)

    assert refused.status_code == 400
    assert "Someone other than" in refused.json()["detail"]


async def test_a_comms_officer_cannot_send_at_all(
    client: httpx.AsyncClient, session: AsyncSession, world: World, people: None, comms: dict
) -> None:
    await make_officer(session, world.ward, PartyRoleName.COMMS_OFFICER, username="pili")
    other = auth(await sign_in(client, "pili"))
    drafted = await _draft(client, comms)

    refused = await client.post(f"{MESSAGES}{drafted['id']}/send/", headers=other)

    assert refused.status_code == 403


@pytest.fixture
def secret(monkeypatch: pytest.MonkeyPatch, fresh_settings: None) -> str:
    value = secrets.token_urlsafe(16)
    monkeypatch.setenv("SMS_CALLBACK_SECRET", value)
    return value


async def test_stop_after_a_party_text_opts_the_number_out_of_party_texts(
    client: httpx.AsyncClient, people: None, comms: dict, admin_headers: dict, secret: str
) -> None:
    first = await _draft(client, comms)
    await client.post(f"{MESSAGES}{first['id']}/send/", headers=admin_headers)

    stop = await client.post(f"/api/sms/{secret}/inbound/", data=RECORDED["inbound_stop"])
    preview = await client.post(f"{MESSAGES}preview/", json={"audience": "members"}, headers=comms)

    assert stop.json()["action"] == "opted_out"
    assert preview.json() == {"recipients": 0, "opted_out": 1}


async def test_a_constituency_limits_the_count_and_the_recipients_and_names_the_place(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    comms: dict,
    admin_headers: dict,
) -> None:
    kasarani = Constituency(county_id=world.county.id, name="Kasarani", code="999")
    session.add(kasarani)
    await session.flush()
    elsewhere = Ward(constituency_id=kasarani.id, name="Mwiki", code="9991")
    session.add(elsewhere)
    await session.flush()
    outside = _member(world, "+254712000009", sms=True)
    outside.ward_id = elsewhere.id
    session.add_all([_member(world, STOPPER, sms=True), outside])
    await session.commit()
    place = {"audience": "members", "constituency": str(world.constituency.id)}

    whole_county = await client.post(
        f"{MESSAGES}preview/",
        json={"audience": "members", "county": str(world.county.id)},
        headers=comms,
    )
    counted = await client.post(f"{MESSAGES}preview/", json=place, headers=comms)
    wrong_ward = await client.post(
        f"{MESSAGES}preview/", json={**place, "ward": str(elsewhere.id)}, headers=comms
    )
    drafted = await client.post(MESSAGES, json={**place, "body": "Meet Saturday."}, headers=comms)
    sent = await client.post(f"{MESSAGES}{drafted.json()['id']}/send/", headers=admin_headers)
    logged = list(await session.scalars(select(SmsLog.phone)))

    assert whole_county.json()["recipients"] == 2
    assert counted.json()["recipients"] == 1
    assert wrong_ward.status_code == 400
    assert drafted.json()["targeted"] == 1
    assert drafted.json()["place"] == world.constituency.name
    assert sent.json()["recipients"] == 1
    assert logged == [STOPPER]
