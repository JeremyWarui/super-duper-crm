"""Candidate profiles on the website and the volunteers their page signs up for the campaign."""

from datetime import UTC, datetime, time, timedelta

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Aspirant,
    AspirantStatus,
    Campaign,
    CandidateProfile,
    OrganisationType,
    PartyRoleName,
    Seat,
    VolunteerProfile,
)
from backend.services.candidates import slug as slug_of
from tests.conftest import World
from tests.factories import TEST_TODAY, make_officer, make_rival_campaign

PROFILE = {"slogan": "Roysambu first", "bio": "Teacher.", "published": True}


async def _aspirant(
    session: AsyncSession,
    world: World,
    *,
    username: str = "ofisa",
    campaign: Campaign | None = None,
    workspace: bool = True,
) -> Aspirant:
    member_id = (await make_officer(session, world.ward, username=username)).party_member_id
    aspirant = Aspirant(
        member_id=member_id,
        seat=Seat.MP,
        constituency_id=world.constituency.id,
        status=AspirantStatus.APPROVED,
        campaign_id=(campaign or world.campaign).id if workspace else None,
    )
    session.add(aspirant)
    await session.commit()
    return aspirant


async def _publish(client, admin_headers, aspirant: Aspirant, **profile) -> None:
    body = {**PROFILE, **profile}
    answer = await client.put(
        f"/api/admin/party/candidates/{aspirant.id}/profile/", headers=admin_headers, json=body
    )
    assert answer.status_code == 200, answer.text


async def _slug(client) -> str:
    (card,) = (await client.get("/api/candidates/")).json()
    return card["slug"]


async def _page(session: AsyncSession, world: World) -> str:
    """A listed candidate page, published without the party console; its slug."""
    aspirant = await _aspirant(session, world)
    session.add(
        CandidateProfile(campaign_id=aspirant.campaign_id, aspirant_id=aspirant.id, **PROFILE)
    )
    await session.commit()
    await session.refresh(aspirant, ["constituency"])
    return slug_of(aspirant)


def _volunteer(world: World, **overrides) -> dict:
    return {
        "first_name": "Wanjiku",
        "last_name": "Njeri",
        "email": "wanjiku@example.com",
        "phone": "0712 345678",
        "ward": str(world.ward.id),
        "registration_centre": str(world.centre.id),
        "profession": "teacher",
        "areas": ["door_to_door"],
        "preferred_contact": "sms",
        "consent_given": True,
        **overrides,
    }


@pytest.mark.party_only
async def test_only_approved_aspirants_with_a_published_profile_are_listed(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    shown = await _aspirant(session, world, username="shown")
    rival = await make_rival_campaign(session, world.ward, owner="drafter")
    draft = await _aspirant(session, world, username="draft", campaign=rival)
    await _publish(client, admin_headers, shown)
    await _publish(client, admin_headers, draft, published=False)
    draft.status = AspirantStatus.WITHDRAWN
    await session.commit()
    before = (await client.get("/api/candidates/")).json()

    shown.status = AspirantStatus.SUSPENDED
    await session.commit()
    filtered = (await client.get("/api/candidates/?seat=mca&county=&q=")).json()
    after = (await client.get("/api/candidates/")).json()

    assert [(c["name"], c["area"], c["county"]) for c in before] == [
        ("Officer shown", "Roysambu", "Nairobi City")
    ]
    assert before[0]["slug"].startswith("mp-roysambu-")
    assert filtered == []
    assert after == []


@pytest.mark.party_only
async def test_the_profile_lists_only_published_upcoming_events_naming_the_aspirant(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    aspirant = await _aspirant(session, world)
    await _publish(client, admin_headers, aspirant)
    ids = {}
    for title, day, published in (
        ("Town hall", TEST_TODAY + timedelta(days=3), True),
        ("Past rally", TEST_TODAY - timedelta(days=3), True),
        ("Draft meeting", TEST_TODAY + timedelta(days=5), False),
        ("Unnamed event", TEST_TODAY + timedelta(days=4), True),
    ):
        body = {"kind": "event", "title": title, "event_date": str(day), "published": published}
        post = await client.post("/api/admin/party/posts/", headers=admin_headers, json=body)
        ids[title] = post.json()["id"]
    for title in ("Town hall", "Past rally", "Draft meeting"):
        named = await client.put(
            f"/api/admin/party/posts/{ids[title]}/aspirants/",
            headers=admin_headers,
            json={"aspirant_ids": [str(aspirant.id)]},
        )
        assert named.status_code == 200

    from backend.models import Event

    session.add(
        Event(
            campaign_id=world.campaign.id,
            ward_id=world.ward.id,
            title="Campaign rally",
            scheduled_date=datetime.combine(TEST_TODAY + timedelta(days=2), time(10), UTC),
        )
    )
    await session.commit()

    detail = (await client.get(f"/api/candidates/{await _slug(client)}/")).json()

    assert [e["title"] for e in detail["events"]] == ["Town hall"]
    assert detail["volunteering_open"] is True
    assert {w["name"] for w in detail["wards"]} == {"Zimmerman", "Githurai"}


@pytest.mark.party_only
async def test_a_page_waits_for_the_aspirants_workspace(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    aspirant = await _aspirant(session, world, workspace=False)

    refused = await client.put(
        f"/api/admin/party/candidates/{aspirant.id}/profile/", headers=admin_headers, json=PROFILE
    )

    assert refused.status_code == 400
    assert "workspace" in refused.json()["detail"]
    assert await session.scalar(select(func.count()).select_from(CandidateProfile)) == 0


async def test_a_standalone_campaign_has_a_profile_with_no_aspirant(
    session: AsyncSession, world: World
) -> None:
    session.add(CandidateProfile(campaign_id=world.campaign.id, **PROFILE))
    await session.commit()

    assert await session.scalar(select(CandidateProfile.aspirant_id)) is None


async def test_a_profile_without_a_campaign_fails_at_the_database(
    session: AsyncSession, world: World
) -> None:
    aspirant = await _aspirant(session, world)
    session.add(CandidateProfile(aspirant_id=aspirant.id, **PROFILE))

    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.parametrize(
    "missing",
    [
        {"first_name": ""},
        {"last_name": ""},
        {"email": ""},
        {"phone": ""},
        {"ward": None},
        {"registration_centre": None},
        {"profession": None},
        {"profession": "other", "profession_other": ""},
        {"areas": []},
        {"areas": ["other"], "area_other": ""},
        {"preferred_contact": None},
        {"consent_given": False},
    ],
)
async def test_the_volunteer_form_refuses_any_missing_field_and_stores_nothing(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    admin_headers: dict,
    missing: dict,
) -> None:
    slug = await _page(session, world)

    answer = await client.post(
        f"/api/candidates/{slug}/volunteer/", json=_volunteer(world, **missing)
    )

    assert answer.status_code in (400, 422)
    assert await session.scalar(select(func.count()).select_from(VolunteerProfile)) == 0


async def test_a_ward_or_centre_outside_the_seat_is_refused(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    slug = await _page(session, world)
    from backend.models import Constituency, Ward

    elsewhere = Ward(
        constituency=Constituency(county=world.county, name="Kasarani", code="280"),
        name="Mwiki",
        code="1400",
    )
    session.add(elsewhere)
    await session.commit()

    outside = await client.post(
        f"/api/candidates/{slug}/volunteer/", json=_volunteer(world, ward=str(elsewhere.id))
    )
    wrong_centre = await client.post(
        f"/api/candidates/{slug}/volunteer/", json=_volunteer(world, ward=str(world.other_ward.id))
    )

    assert (outside.status_code, wrong_centre.status_code) == (400, 400)


async def test_a_known_phone_gets_the_same_answer_and_no_second_row(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    slug = await _page(session, world)

    first = await client.post(f"/api/candidates/{slug}/volunteer/", json=_volunteer(world))
    again = await client.post(
        f"/api/candidates/{slug}/volunteer/", json=_volunteer(world, first_name="Other")
    )
    rows = await session.scalar(
        select(func.count())
        .select_from(VolunteerProfile)
        .where(VolunteerProfile.campaign_id == world.campaign.id)
    )

    assert (first.status_code, again.status_code) == (201, 201)
    assert first.json()["message"] == again.json()["message"]
    assert len(first.json()["withdraw_code"]) == len(again.json()["withdraw_code"]) > 0
    assert rows == 1


async def test_the_candidate_and_manager_see_and_move_the_campaigns_volunteers(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    admin_headers: dict,
    organisation_type: OrganisationType,
) -> None:
    slug = await _page(session, world)
    await client.post(f"/api/candidates/{slug}/volunteer/", json=_volunteer(world))
    path = f"/api/campaigns/{world.campaign.id}/volunteers/"
    from tests.factories import make_rival_campaign

    rival = await make_rival_campaign(session, world.ward)
    session.add(
        VolunteerProfile(
            campaign_id=rival.id,
            first_name="Rival",
            last_name="Helper",
            phone="+254700000001",
            ward_id=world.ward.id,
            preferred_contact="sms",
            consent_wording="Rival wording.",
            consent_at=datetime.now(UTC),
        )
    )
    await session.commit()

    listed = await client.get(path, headers=world.headers("manager"))
    (row,) = listed.json()
    moved = await client.patch(
        f"{path}{row['id']}/",
        headers=world.headers("manager"),
        json={"status": "active", "availability_notes": "Weekends"},
    )
    candidate = await client.get(path, headers=world.headers("candidate"))
    mobilizer = await client.get(path, headers=world.headers("mobilizer"))
    other = await client.get(
        f"/api/campaigns/{rival.id}/volunteers/", headers=world.headers("manager")
    )
    party_register = await client.get("/api/party/volunteers/", headers=admin_headers)

    assert (row["first_name"], row["ward"]["name"]) == ("Wanjiku", "Zimmerman")
    assert len(listed.json()) == 1
    assert (moved.json()["status"], moved.json()["availability_notes"]) == ("active", "Weekends")
    assert (candidate.status_code, mobilizer.status_code, other.status_code) == (200, 403, 404)
    if organisation_type is OrganisationType.PARTY:
        assert party_register.json()["total"] == 0
    else:
        assert party_register.status_code == 404


async def test_withdrawal_deletes_and_answers_the_same_for_any_code(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    slug = await _page(session, world)
    done = await client.post(f"/api/candidates/{slug}/volunteer/", json=_volunteer(world))

    real = await client.post(f"/api/candidates/volunteer/withdraw/{done.json()['withdraw_code']}/")
    fake = await client.post("/api/candidates/volunteer/withdraw/not-a-code/")
    left = await session.scalar(select(func.count()).select_from(VolunteerProfile))

    assert real.json() == fake.json()
    assert left == 0


async def test_deleting_the_campaign_deletes_its_volunteers(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    slug = await _page(session, world)
    await client.post(f"/api/candidates/{slug}/volunteer/", json=_volunteer(world))

    await session.delete(world.campaign)
    await session.commit()
    left = await session.scalar(select(func.count()).select_from(VolunteerProfile))

    assert left == 0


@pytest.mark.party_only
async def test_an_officer_holding_a_party_office_is_not_the_website_editor(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    aspirant = await _aspirant(session, world)
    from tests.factories import auth, sign_in

    await make_officer(session, world.ward, PartyRoleName.NOMINATIONS_OFFICER, username="teuzi")
    headers = auth(await sign_in(client, "teuzi"))

    answer = await client.put(
        f"/api/admin/party/candidates/{aspirant.id}/profile/", headers=headers, json=PROFILE
    )

    assert answer.status_code == 403
