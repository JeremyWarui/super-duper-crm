"""The public party application and withdrawal."""

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    AuditEvent,
    PartyMember,
    PartyMemberStatus,
    PartyRequest,
    PartyRoleName,
    VolunteerProfile,
    VolunteerStatus,
)
from backend.services.consent import MEMBER_SMS_WORDING
from backend.services.membership import process_requests
from tests.conftest import World
from tests.factories import TEST_PASSWORD, auth, make_officer, sign_in

pytestmark = pytest.mark.party_only


def _application(world: World, **overrides) -> dict:
    return {
        "first_name": "Wanjiru",
        "surname": "Kamau",
        "phone": "0712 345678",
        "email": "wanjiru@example.com",
        "password": TEST_PASSWORD,
        "ward": str(world.centre.ward_id),
        "registration_centre": str(world.centre.id),
        "consent_given": True,
        **overrides,
    }


async def test_an_application_without_consent_is_refused(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    refused = await client.post("/api/party/join/", json=_application(world, consent_given=False))

    assert refused.status_code == 400
    assert (await session.scalars(select(PartyMember))).all() == []


async def test_a_repeat_phone_answers_like_a_new_one_and_leaves_the_member_alone(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    new = await client.post("/api/party/join/", json=_application(world))
    await process_requests(session)
    member = await session.scalar(select(PartyMember))
    member.status = PartyMemberStatus.APPROVED
    await session.commit()
    code = member.withdraw_code

    repeat = await client.post(
        "/api/party/join/", json=_application(world, first_name="Someone", surname="Else")
    )
    await process_requests(session)
    await session.refresh(member)

    assert (repeat.status_code, set(repeat.json())) == (new.status_code, set(new.json()))
    assert repeat.json()["withdraw_url"].startswith("/party/withdraw/")
    assert repeat.json()["withdraw_url"] != new.json()["withdraw_url"]
    assert (member.full_name, member.status, member.withdraw_code) == (
        "Wanjiru Kamau",
        PartyMemberStatus.APPROVED,
        code,
    )


async def test_the_place_picker_walks_county_constituency_ward_without_a_login(
    client: httpx.AsyncClient, world: World
) -> None:
    counties = (await client.get("/api/party/places/")).json()
    constituencies = (await client.get(f"/api/party/places/?county={world.county.id}")).json()
    wards = (await client.get(f"/api/party/places/?constituency={world.constituency.id}")).json()

    assert str(world.county.id) in [c["id"] for c in counties]
    assert [c["name"] for c in constituencies] == ["Roysambu"]
    assert [w["name"] for w in wards] == ["Githurai", "Zimmerman"]


async def test_a_public_join_only_queues_a_request_until_the_inbox_is_applied(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await client.post("/api/party/join/", json=_application(world))
    queued = (await session.scalars(select(PartyRequest))).all()
    before = (await session.scalars(select(PartyMember))).all()

    await process_requests(session)
    member = await session.scalar(select(PartyMember))

    assert (len(queued), before) == (1, [])
    assert (member.status, member.phone) == (PartyMemberStatus.PENDING, "+254712345678")
    assert (await session.scalars(select(PartyRequest))).all() == []


async def test_opening_the_members_page_applies_a_waiting_join(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await client.post("/api/party/join/", json=_application(world))
    await make_officer(session, world.ward, PartyRoleName.MEMBERSHIP_OFFICER)
    headers = auth(await sign_in(client, "ofisa"))

    members = (await client.get("/api/party/members/", headers=headers)).json()

    assert ("Wanjiru Kamau", "pending") in {(m["full_name"], m["status"]) for m in members["items"]}


async def test_the_members_own_link_withdraws_them_once_and_is_audited_as_public(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    joined = await client.post("/api/party/join/", json=_application(world))
    code = joined.json()["withdraw_url"].rsplit("/", 1)[1]

    first = await client.post(f"/api/party/withdraw/{code}/")
    second = await client.post(f"/api/party/withdraw/{code}/")
    await process_requests(session)
    member = await session.scalar(select(PartyMember))
    events = (await session.scalars(select(AuditEvent))).all()

    assert first.json() == second.json()
    assert (member.status, member.withdraw_code) == (PartyMemberStatus.WITHDRAWN, None)
    assert [(e.action, e.actor_name, e.detail) for e in events] == [
        ("member.withdraw", "public", {"from": "pending", "to": "withdrawn"})
    ]


def _volunteer(**overrides) -> dict:
    return {
        "profession": "teacher",
        "areas": ["door_to_door", "barazas"],
        "preferred_contact": "whatsapp",
        "consent_given": True,
        **overrides,
    }


async def test_a_volunteer_withdrawal_leaves_the_membership_approved(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    joined = await client.post("/api/party/join/", json=_application(world, volunteer=_volunteer()))
    await process_requests(session)
    member = await session.scalar(select(PartyMember))
    member.status = PartyMemberStatus.APPROVED
    await session.commit()
    code = joined.json()["volunteer_withdraw_url"].rsplit("/", 1)[1]

    done = await client.post(f"/api/party/volunteer/withdraw/{code}/")
    await process_requests(session)
    profile = await session.scalar(select(VolunteerProfile))
    await session.refresh(member)

    assert done.status_code == 200
    assert code != joined.json()["withdraw_url"].rsplit("/", 1)[1]
    assert (profile.status, member.status) == (
        VolunteerStatus.WITHDRAWN,
        PartyMemberStatus.APPROVED,
    )


async def test_a_volunteer_section_without_its_consent_queues_nothing(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    refused = await client.post(
        "/api/party/join/", json=_application(world, volunteer=_volunteer(consent_given=False))
    )

    assert refused.status_code == 400
    assert (await session.scalars(select(PartyRequest))).all() == []


async def test_a_join_with_a_members_phone_cannot_take_over_their_volunteer_profile(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await client.post("/api/party/join/", json=_application(world, volunteer=_volunteer()))
    await process_requests(session)
    member = await session.scalar(select(PartyMember))
    profile = await session.scalar(select(VolunteerProfile))
    member.status, profile.status = PartyMemberStatus.APPROVED, VolunteerStatus.ACTIVE
    await session.commit()
    owner_code = profile.withdraw_code

    stranger = await client.post(
        "/api/party/join/",
        json=_application(world, volunteer=_volunteer(areas=["fundraising"])),
    )
    await process_requests(session)
    stranger_code = stranger.json()["volunteer_withdraw_url"].rsplit("/", 1)[1]
    await client.post(f"/api/party/volunteer/withdraw/{stranger_code}/")
    await process_requests(session)
    await session.refresh(profile)

    assert (profile.status, profile.interests, profile.withdraw_code) == (
        VolunteerStatus.ACTIVE,
        ["door_to_door", "barazas"],
        owner_code,
    )


async def test_a_join_with_a_members_phone_does_not_sign_them_up_to_volunteer(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await client.post("/api/party/join/", json=_application(world))
    await process_requests(session)
    member = await session.scalar(select(PartyMember))
    member.status = PartyMemberStatus.APPROVED
    await session.commit()

    await client.post(
        "/api/party/join/",
        json=_application(world, volunteer=_volunteer()),
    )
    await process_requests(session)

    assert (await session.scalars(select(VolunteerProfile))).all() == []


async def test_a_join_stores_the_volunteers_details_and_never_queues_the_password(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    volunteer = _volunteer(profession="other", profession_other="Boda rider")
    await client.post(
        "/api/party/join/",
        json=_application(
            world, volunteer={**volunteer, "areas": ["other"], "area_other": "Music"}
        ),
    )
    queued = await session.scalar(select(PartyRequest))
    await process_requests(session)
    member = await session.scalar(select(PartyMember))
    profile = await session.scalar(select(VolunteerProfile))

    assert TEST_PASSWORD not in str(queued.payload)
    assert queued.payload["password_hash"].startswith("$argon2")
    assert (member.first_name, member.full_name, member.email, member.registration_centre_id) == (
        "Wanjiru",
        "Wanjiru Kamau",
        "wanjiru@example.com",
        world.centre.id,
    )
    assert (
        profile.member_id,
        profile.last_name,
        profile.registration_centre_id,
        profile.profession,
        profile.profession_other,
        profile.interests,
        profile.interest_other,
    ) == (member.id, "Kamau", world.centre.id, "other", "Boda rider", ["other"], "Music")


async def test_a_join_refuses_a_missing_detail_or_a_station_outside_the_ward(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    complete = _application(world)
    refused = [
        {k: v for k, v in complete.items() if k != "email"},
        {k: v for k, v in complete.items() if k != "password"},
        {**complete, "ward": str(world.other_ward.id)},
        _application(world, volunteer=_volunteer(profession="other")),
        _application(world, volunteer=_volunteer(areas=["other"])),
    ]

    answers = [(await client.post("/api/party/join/", json=body)).status_code for body in refused]

    assert answers == [400] * len(refused)
    assert (await session.scalars(select(PartyRequest))).all() == []


async def test_the_place_picker_lists_a_wards_polling_stations(
    client: httpx.AsyncClient, world: World
) -> None:
    centres = (await client.get(f"/api/party/places/?ward={world.centre.ward_id}")).json()

    assert centres == [{"id": str(world.centre.id), "name": "Zimmerman Primary"}]


async def test_the_sms_tick_box_records_its_wording_and_is_off_unless_ticked(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await client.post("/api/party/join/", json=_application(world, sms_updates=True))
    await client.post(
        "/api/party/join/", json=_application(world, phone="0712 000111", email="b@example.com")
    )
    await process_requests(session)
    rows = (await session.execute(select(PartyMember.phone, PartyMember.sms_consent_wording))).all()

    assert sorted(rows) == [
        ("+254712000111", None),
        ("+254712345678", MEMBER_SMS_WORDING),
    ]
