"""The party coordination workspace, its coordinators' member register and recruitment links."""

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    AuditEvent,
    Campaign,
    CampaignMember,
    CampaignMemberArea,
    OfficeLevel,
    PartyConsentChannel,
    PartyMember,
    PartyMemberStatus,
    Supporter,
    Target,
    User,
    UserRole,
    Ward,
    WorkspaceKind,
)
from backend.services import privacy
from backend.services.accounts import add_member
from backend.services.errors import Refused
from backend.services.membership import process_requests
from tests.conftest import World
from tests.factories import TEST_PASSWORD, auth, claim_link, make_user, sign_in, site_settings

pytestmark = pytest.mark.party_only

URL = "/api/party/workspace/"


async def _workspace(
    session: AsyncSession, client: httpx.AsyncClient, admin_headers: dict
) -> tuple[Campaign, str]:
    """The party workspace, and the password its Workspace Manager (wm@example.com) chose
    through their invite link."""
    session.add(site_settings(name="Umoja Party"))
    await session.commit()
    created = await client.post(
        URL,
        headers=admin_headers,
        json={"manager": {"username": "wm-amani", "email": "wm@example.com"}},
    )
    assert created.status_code == 201, created.text
    campaign = await session.get(Campaign, uuid.UUID(created.json()["id"]))
    assert created.json()["invite"] == "email"
    await claim_link(client, session, "wm@example.com")
    return campaign, TEST_PASSWORD


async def _coordinator(
    session: AsyncSession, client: httpx.AsyncClient, campaign: Campaign, ward: Ward, name: str
) -> dict[str, str]:
    user = await make_user(session, username=name, role=UserRole.COORDINATOR)
    member = await add_member(session, campaign.id, user)
    await session.flush()
    session.add(CampaignMemberArea(campaign_member_id=member.id, ward_id=ward.id))
    await session.commit()
    return auth(await sign_in(client, name))


def _member(name: str, phone: str, ward: Ward, **fields) -> PartyMember:
    return PartyMember(
        full_name=name,
        phone=phone,
        ward_id=ward.id,
        status=PartyMemberStatus.APPROVED,
        consent_wording="Wording.",
        consent_channel=PartyConsentChannel.WEB_FORM,
        consent_at=datetime.now(UTC),
        **fields,
    )


async def test_the_console_replaces_the_workspace_manager_and_the_old_one_is_signed_out(
    session: AsyncSession, client: httpx.AsyncClient, world: World, admin_headers: dict
) -> None:
    campaign, password = await _workspace(session, client, admin_headers)
    old = auth(await sign_in(client, "wm@example.com", password))
    refused = await client.post(
        f"{URL}manager/", headers=old, json={"manager": {"username": "wm-sneaky"}}
    )

    replaced = await client.post(
        f"{URL}manager/",
        headers=admin_headers,
        json={"manager": {"username": "wm-baraka", "email": "baraka@example.com"}},
    )
    new = auth(await claim_link(client, session, "baraka@example.com"))

    assert refused.status_code == 403
    assert replaced.status_code == 200, replaced.text
    assert (replaced.json()["replaced"], replaced.json()["invite"]) == ("wm-amani", "email")
    assert (await client.get("/api/auth/me/", headers=old)).status_code == 401
    assert (await client.get(f"/api/campaigns/{campaign.id}/", headers=new)).status_code == 200
    assert (await client.get(URL, headers=admin_headers)).json()["managers"] == ["wm-baraka"]


async def test_the_party_has_one_national_workspace_targeting_every_ward(
    session: AsyncSession, client: httpx.AsyncClient, world: World, admin_headers: dict
) -> None:
    campaign, password = await _workspace(session, client, admin_headers)
    again = await client.post(URL, headers=admin_headers, json={"manager": {"username": "wm-2"}})
    targets = await session.scalar(
        select(func.count(Target.id)).where(Target.campaign_id == campaign.id)
    )
    wards = await session.scalar(select(func.count(Ward.id)))
    read = (await client.get(URL, headers=admin_headers)).json()
    shown = (
        await client.get(
            f"/api/campaigns/{campaign.id}/",
            headers=auth(await sign_in(client, "wm@example.com", password)),
        )
    ).json()

    session.add(
        Campaign(title="Second", kind=WorkspaceKind.PARTY, office_level=OfficeLevel.NATIONAL)
    )
    with pytest.raises(IntegrityError):
        await session.commit()

    assert (again.status_code, again.json()["detail"]) == (
        400,
        "The party already has its workspace.",
    )
    assert targets == wards == 2
    assert read["managers"] == ["wm-amani"]
    assert (shown["candidate_name"], shown["seat"], shown["kind"]) == (
        "Umoja Party",
        "National",
        "party",
    )


async def test_a_staff_login_on_the_party_workspace_fails_at_the_database(
    session: AsyncSession, client: httpx.AsyncClient, world: World, admin_headers: dict
) -> None:
    campaign, password = await _workspace(session, client, admin_headers)
    staff = User(username="ofisa", role=None)
    session.add(staff)
    await session.flush()

    session.add(CampaignMember(campaign_id=campaign.id, user_id=staff.id, role=UserRole.MANAGER))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_the_dashboard_counts_the_party_workspace_apart_from_hosted_ones(
    session: AsyncSession, client: httpx.AsyncClient, world: World, admin_headers: dict
) -> None:
    campaign, password = await _workspace(session, client, admin_headers)
    session.add(
        Supporter(campaign_id=campaign.id, ward_id=world.ward.id, full_name="P", phone="+2547001")
    )
    await session.commit()

    body = (await client.get("/api/party/dashboard/", headers=admin_headers)).json()

    assert body["active_campaigns"] == 1
    assert [row["seat"] for row in body["campaigns_by_county_and_seat"]] == ["mp"]
    assert body["party_workspace"] == {"supporters": 1, "mobilizers": 0, "upcoming_events": 0}


async def test_party_workspace_rows_never_reach_a_hosted_workspace(
    session: AsyncSession, client: httpx.AsyncClient, world: World, admin_headers: dict
) -> None:
    campaign, password = await _workspace(session, client, admin_headers)
    session.add(
        Supporter(campaign_id=campaign.id, ward_id=world.ward.id, full_name="P", phone="+2547001")
    )
    await session.commit()

    seen = [
        (await client.get(path, headers=world.headers("manager"))).json()
        for path in ("/api/supporters/", f"/api/supporters/?campaign={campaign.id}")
    ]
    targets = (
        await client.get(f"/api/targets/?campaign={campaign.id}", headers=world.headers("manager"))
    ).json()

    assert seen == [[], []]
    assert targets == []


async def test_a_coordinator_reads_members_only_in_their_area_audited_and_without_export(
    session: AsyncSession, client: httpx.AsyncClient, world: World, admin_headers: dict
) -> None:
    campaign, password = await _workspace(session, client, admin_headers)
    session.add_all(
        [
            _member("Inside Area", "+254711000001", world.ward),
            _member("Outside Area", "+254711000002", world.other_ward),
        ]
    )
    await session.commit()
    head = await _coordinator(session, client, campaign, world.ward, "otieno")

    page = (await client.get(f"{URL}members/", headers=head)).json()
    export = await client.get("/api/party/members/export.csv", headers=head)
    audited = await session.scalar(
        select(func.count(AuditEvent.id)).where(AuditEvent.action == "members.area_read")
    )

    assert [m["full_name"] for m in page["members"]] == ["Inside Area"]
    assert page["total"] == 1
    assert set(page["members"][0]) == {
        "id",
        "full_name",
        "phone",
        "status",
        "ward",
        "ward_name",
        "registration_centre",
        "registration_centre_name",
    }
    assert export.status_code == 403
    assert audited == 1


async def test_a_hosted_workspace_coordinator_gets_404_on_the_register(
    session: AsyncSession, client: httpx.AsyncClient, world: World, admin_headers: dict
) -> None:
    await _workspace(session, client, admin_headers)
    head = await _coordinator(session, client, world.campaign, world.ward, "hosted-co")

    answers = [
        (await client.get(f"{URL}{path}", headers=head)).status_code
        for path in ("members/", "recruitment/")
    ]

    assert answers == [404, 404]


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


async def test_a_recruitment_code_records_the_recruiter_and_county_but_never_approves(
    session: AsyncSession, client: httpx.AsyncClient, world: World, admin_headers: dict
) -> None:
    campaign, password = await _workspace(session, client, admin_headers)
    head = await _coordinator(session, client, campaign, world.ward, "otieno")
    code = (await client.get(f"{URL}recruitment/", headers=head)).json()["code"]

    joined = await client.post("/api/party/join/", json=_application(world, recruitment=code))
    await process_requests(session)
    member = await session.scalar(select(PartyMember).where(PartyMember.phone == "+254712345678"))
    recruiter = await session.scalar(
        select(CampaignMember.id)
        .where(CampaignMember.campaign_id == campaign.id)
        .where(CampaignMember.role == UserRole.COORDINATOR)
    )
    counts = (await client.get(f"{URL}recruitment/", headers=head)).json()
    dashboard = (await client.get("/api/party/dashboard/", headers=admin_headers)).json()

    assert joined.status_code == 201
    assert member.status is PartyMemberStatus.PENDING
    assert (member.recruited_by_id, member.recruitment_county_id) == (recruiter, world.county.id)
    assert (counts["code"], counts["by_status"]["pending"]) == (code, 1)
    assert dashboard["applications_by_county"][0]["count"] == 1
    assert dashboard["applications_by_coordinator"] == [
        {"coordinator": "Amina Kariuki", "count": 1}
    ]


@pytest.mark.parametrize("code", ["no-such-code", "retired", "turned-off"])
async def test_an_unknown_retired_or_turned_off_code_still_accepts_the_application_alone(
    session: AsyncSession,
    client: httpx.AsyncClient,
    world: World,
    admin_headers: dict,
    code: str,
) -> None:
    campaign, password = await _workspace(session, client, admin_headers)
    head = await _coordinator(session, client, campaign, world.ward, "otieno")
    if code == "retired":
        code = (await client.get(f"{URL}recruitment/", headers=head)).json()["code"]
        await client.post(f"{URL}recruitment/", headers=head)
    if code == "turned-off":
        code = (await client.get(f"{URL}recruitment/", headers=head)).json()["code"]
        coordinator = await session.scalar(select(User).where(User.username == "otieno"))
        coordinator.is_active = False
        await session.commit()

    joined = await client.post("/api/party/join/", json=_application(world, recruitment=code))
    await process_requests(session)
    member = await session.scalar(select(PartyMember).where(PartyMember.phone == "+254712345678"))

    assert joined.status_code == 201
    assert (member.status, member.recruited_by_id, member.recruitment_county_id) == (
        PartyMemberStatus.PENDING,
        None,
        None,
    )


async def test_the_party_workspace_is_never_closed(
    session: AsyncSession, client: httpx.AsyncClient, world: World, admin_headers: dict
) -> None:
    campaign, password = await _workspace(session, client, admin_headers)
    manager = auth(await sign_in(client, "wm@example.com", password))

    by_manager = await client.post(f"/api/campaigns/{campaign.id}/data/close/", headers=manager)
    await session.refresh(campaign)
    actor = await session.scalar(select(User).where(User.username == "wm-amani"))

    assert by_manager.status_code == 403
    with pytest.raises(Refused, match="never closed"):
        privacy.close(session, campaign, actor=actor)
    assert campaign.closed_at is None
