"""The party dashboard counts what its design says, follows its filters, and is the superuser's."""

from datetime import UTC, datetime, time, timedelta

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Aspirant,
    AspirantStatus,
    Campaign,
    Constituency,
    ContactMethod,
    County,
    Event,
    EventStatus,
    OfficeLevel,
    PartyConsentChannel,
    PartyMember,
    PartyMemberStatus,
    PartyRoleName,
    Seat,
    VolunteerProfile,
    VolunteerStatus,
    Ward,
    WorkspaceKind,
)
from tests.conftest import World
from tests.factories import TEST_TODAY, auth, make_officer, make_rival_campaign, sign_in

pytestmark = pytest.mark.party_only

URL = "/api/party/dashboard/"


def _member(ward: Ward, phone: str, status=PartyMemberStatus.APPROVED) -> PartyMember:
    return PartyMember(
        full_name=f"Member {phone}",
        phone=phone,
        ward_id=ward.id,
        status=status,
        consent_channel=PartyConsentChannel.WEB_FORM,
        consent_wording="I agree.",
        consent_at=datetime.now(UTC),
    )


def _volunteer(
    member: PartyMember, interests: list[str], status=VolunteerStatus.ACTIVE
) -> VolunteerProfile:
    return VolunteerProfile(
        member=member,
        first_name="Member",
        last_name="",
        phone=member.phone,
        ward_id=member.ward_id,
        status=status,
        interests=interests,
        preferred_contact=ContactMethod.CALL,
        consent_wording="I agree.",
        consent_at=datetime.now(UTC),
    )


def _event(campaign: Campaign, ward: Ward, days: int, status=EventStatus.PLANNED) -> Event:
    day = TEST_TODAY + timedelta(days=days)
    return Event(
        campaign_id=campaign.id,
        ward_id=ward.id,
        title="Town hall",
        status=status,
        scheduled_date=datetime.combine(day, time(12), tzinfo=UTC),
    )


@pytest.fixture
async def nakuru(session: AsyncSession, world: World) -> dict:
    """Nairobi City: the world's MP campaign with an approved aspirant, an MP campaign whose
    aspirant is suspended, and an MCA campaign with no aspirant. Nakuru: an MCA campaign.
    Members, volunteers and events in both."""
    county = County(name="Nakuru", code="032")
    ward = Ward(constituency=Constituency(county=county, name="Naivasha"), name="Viwandani")
    session.add(county)
    await session.flush()
    rival = await make_rival_campaign(session, ward, title="Nakuru MCA", owner="nakuru")
    standalone = Campaign(
        title="Standalone MCA", office_level=OfficeLevel.WARD, ward_id=world.other_ward.id
    )
    held = Campaign(
        title="Held MP",
        office_level=OfficeLevel.CONSTITUENCY,
        seat=Seat.MP,
        constituency_id=world.constituency.id,
    )
    session.add_all([standalone, held])

    leader = _member(world.ward, "+254700000101")
    session.add_all(
        [
            leader,
            _member(world.ward, "+254700000102"),
            _member(world.ward, "+254700000103", PartyMemberStatus.PENDING),
            _volunteer(leader, ["door_to_door", "mobilising_voters"]),
            _volunteer(_member(ward, "+254700000201"), ["door_to_door"]),
            _volunteer(_member(ward, "+254700000202"), ["fundraising"], VolunteerStatus.INACTIVE),
        ]
    )
    await session.flush()
    held_member = _member(world.ward, "+254700000104")
    session.add(held_member)
    await session.flush()
    for member, status, campaign in (
        (leader, AspirantStatus.APPROVED, world.campaign),
        (held_member, AspirantStatus.SUSPENDED, held),
    ):
        session.add(
            Aspirant(
                member_id=member.id,
                seat=Seat.MP,
                constituency_id=world.constituency.id,
                status=status,
                campaign_id=campaign.id,
                status_reason="Under review." if status is AspirantStatus.SUSPENDED else None,
            )
        )
    session.add_all(
        [
            _event(world.campaign, world.ward, 5),
            _event(world.campaign, world.ward, 5, EventStatus.DONE),
            _event(world.campaign, world.ward, 60),
            _event(rival, ward, 10),
        ]
    )
    await session.commit()
    return {"county": county}


async def test_each_figure_counts_what_the_design_says(
    client: httpx.AsyncClient, admin_headers: dict, world: World, nakuru: dict
) -> None:
    board = (await client.get(URL, headers=admin_headers)).json()

    by_county = {
        (row["county"], row["seat"]): row["count"] for row in board["campaigns_by_county_and_seat"]
    }
    assert {
        name: board[name]
        for name in (
            "approved_members",
            "pending_applications",
            "active_volunteers",
            "approved_aspirants",
            "active_campaigns",
        )
    } == {
        "approved_members": 5,
        "pending_applications": 1,
        "active_volunteers": 2,
        "approved_aspirants": 1,
        "active_campaigns": 3,
    }
    assert [(r["county"], r["count"]) for r in board["volunteers_by_county"]] == [
        ("Nairobi City", 1),
        ("Nakuru", 1),
    ]
    assert [(r["interest"], r["count"]) for r in board["volunteers_by_interest"]] == [
        ("door_to_door", 2),
        ("mobilising_voters", 1),
    ]
    assert [(r["county"], r["count"]) for r in board["upcoming_events_by_county"]] == [
        ("Nairobi City", 1),
        ("Nakuru", 1),
    ]
    assert [(r["seat"], r["count"]) for r in board["upcoming_events_by_seat"]] == [
        ("mca", 1),
        ("mp", 1),
    ]
    assert by_county == {
        ("Nairobi City", "mca"): 1,
        ("Nairobi City", "mp"): 2,
        ("Nakuru", "mca"): 1,
    }


async def test_a_county_filter_drops_another_countys_members_and_campaigns(
    client: httpx.AsyncClient, admin_headers: dict, world: World, nakuru: dict
) -> None:
    board = (
        await client.get(URL, headers=admin_headers, params={"county": str(nakuru["county"].id)})
    ).json()

    assert (board["approved_members"], board["pending_applications"]) == (2, 0)
    assert [r["county"] for r in board["campaigns_by_county_and_seat"]] == ["Nakuru"]


async def test_only_the_superuser_reads_the_dashboard(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    await make_officer(session, world.ward, *PartyRoleName, username="ofisa")
    officer = auth(await sign_in(client, "ofisa"))

    answers = [
        (await client.get(URL, headers=headers)).status_code
        for headers in (
            {},
            world.headers("candidate"),
            world.headers("manager"),
            officer,
            admin_headers,
        )
    ]

    assert answers == [401, 403, 403, 403, 200]


async def test_a_ward_filter_counts_every_event_held_in_that_ward(
    client: httpx.AsyncClient, session: AsyncSession, admin_headers: dict, world: World
) -> None:
    governor = Campaign(
        title="Governor",
        office_level=OfficeLevel.COUNTY,
        seat=Seat.GOVERNOR,
        county_id=world.county.id,
    )
    session.add(governor)
    await session.flush()
    session.add_all([_event(world.campaign, world.ward, 5), _event(governor, world.ward, 3)])
    await session.commit()

    board = (
        await client.get(URL, headers=admin_headers, params={"ward": str(world.ward.id)})
    ).json()

    assert [(r["seat"], r["count"]) for r in board["upcoming_events_by_seat"]] == [
        ("governor", 1),
        ("mp", 1),
    ]


async def test_a_standalone_workspace_counts_as_active_whatever_its_aspirant_says(
    client: httpx.AsyncClient, session: AsyncSession, admin_headers: dict, world: World
) -> None:
    member = await make_officer(session, world.ward, PartyRoleName.MEMBERSHIP_OFFICER)
    session.add(
        Aspirant(
            member_id=member.party_member_id,
            seat=Seat.MP,
            constituency_id=world.constituency.id,
            status=AspirantStatus.SUSPENDED,
            status_reason="Under review.",
            campaign_id=world.campaign.id,
        )
    )
    await session.commit()
    hosted = (await client.get(URL, headers=admin_headers)).json()["active_campaigns"]

    world.campaign.kind = WorkspaceKind.STANDALONE
    await session.commit()
    standalone = (await client.get(URL, headers=admin_headers)).json()["active_campaigns"]

    assert (hosted, standalone) == (0, 1)
