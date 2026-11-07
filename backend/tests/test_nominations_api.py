"""Applying to vie: a timetable the Super Admin publishes, a member's own application inside it,
its fee and documents, and vetting that only an officer, never the applicant, decides."""

import io
import uuid

import httpx
import pytest
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Campaign, PartyMember, PartyMemberStatus, PartyRoleName, Seat, User
from tests.conftest import World
from tests.factories import auth, make_officer, sign_in

pytestmark = pytest.mark.party_only

WINDOWS = "/api/party/nominations/windows/"
MINE = "/api/party/nominations/mine/"


def _timetable(fee: int = 0, opens: str = "2026-10-25", closes: str = "2026-11-10") -> dict:
    return {
        "title": "Nominations 2027",
        "opens_on": opens,
        "closes_on": closes,
        "requirements": "A registered voter in the area.",
        "seats": [{"seat": "mca", "fee_kes": fee}, {"seat": "mp", "fee_kes": 0}],
    }


@pytest.fixture
async def officer(session: AsyncSession, client: httpx.AsyncClient, world: World) -> dict:
    await make_officer(session, world.ward, PartyRoleName.NOMINATIONS_OFFICER, username="teuzi")
    return auth(await sign_in(client, "teuzi"))


@pytest.fixture
async def member(session: AsyncSession, client: httpx.AsyncClient, world: World) -> dict:
    """An approved member's own login, with no party office."""
    await make_officer(session, world.ward, username="mwanachama")
    return auth(await sign_in(client, "mwanachama"))


async def _published(client, officer: dict, admin: dict, **timetable) -> dict:
    drafted = await client.post(WINDOWS, json=_timetable(**timetable), headers=officer)
    assert drafted.status_code == 201, drafted.text
    published = await client.post(f"{WINDOWS}{drafted.json()['id']}/publish/", headers=admin)
    assert published.status_code == 200, published.text
    return published.json()


async def test_publishing_needs_the_super_admin_and_someone_other_than_the_drafter(
    client: httpx.AsyncClient, officer: dict, admin_headers: dict
) -> None:
    by_officer = (await client.post(WINDOWS, json=_timetable(), headers=officer)).json()
    by_admin = (
        await client.post(
            WINDOWS, json=_timetable(opens="2027-01-01", closes="2027-01-31"), headers=admin_headers
        )
    ).json()

    self_published = await client.post(f"{WINDOWS}{by_officer['id']}/publish/", headers=officer)
    own_draft = await client.post(f"{WINDOWS}{by_admin['id']}/publish/", headers=admin_headers)
    published = await client.post(f"{WINDOWS}{by_officer['id']}/publish/", headers=admin_headers)
    public = await client.get("/api/party/nominations/current/")

    assert self_published.status_code == 403
    assert own_draft.status_code == 400
    assert published.json()["status"] == "published"
    assert (public.json()["title"], public.json()["open"]) == ("Nominations 2027", True)


async def test_the_super_admin_cannot_publish_a_draft_they_changed(
    client: httpx.AsyncClient, officer: dict, admin_headers: dict
) -> None:
    drafted = (await client.post(WINDOWS, json=_timetable(), headers=officer)).json()
    revised = await client.put(
        f"{WINDOWS}{drafted['id']}/", json=_timetable(fee=1), headers=admin_headers
    )

    published = await client.post(f"{WINDOWS}{drafted['id']}/publish/", headers=admin_headers)

    assert revised.status_code == 200
    assert (published.status_code, published.json()["detail"]) == (
        400,
        "Someone other than whoever drafted the timetable publishes it.",
    )


async def test_no_application_outside_the_window_and_only_from_an_approved_member(
    client: httpx.AsyncClient,
    session: AsyncSession,
    officer: dict,
    member: dict,
    admin_headers: dict,
) -> None:
    before = await client.post(MINE, json={"seat": "mca"}, headers=member)
    await _published(client, officer, admin_headers, opens="2026-11-05", closes="2026-11-20")
    not_yet = await client.post(MINE, json={"seat": "mca"}, headers=member)

    assert before.status_code == 400
    assert not_yet.status_code == 400
    assert "not open" in not_yet.json()["detail"]


async def test_a_lapsed_member_cannot_apply(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    officer: dict,
    admin_headers: dict,
) -> None:
    applicant = await make_officer(session, world.ward, username="ameondoka")
    headers = auth(await sign_in(client, "ameondoka"))
    await _published(client, officer, admin_headers)
    member = await session.get(PartyMember, applicant.party_member_id)
    member.status = PartyMemberStatus.WITHDRAWN
    await session.commit()

    refused = await client.post(MINE, json={"seat": "mca"}, headers=headers)

    assert refused.status_code in (401, 403)


async def test_one_live_application_per_member(
    client: httpx.AsyncClient, officer: dict, member: dict, admin_headers: dict
) -> None:
    await _published(client, officer, admin_headers)

    first = await client.post(MINE, json={"seat": "mca"}, headers=member)
    second = await client.post(MINE, json={"seat": "mp"}, headers=member)

    assert first.status_code == 201, first.text
    assert (first.json()["application"]["status"], first.json()["application"]["area"]) == (
        "draft",
        "Zimmerman",
    )
    assert second.status_code == 400


def _photo() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (40, 30), "white").save(out, "PNG")
    return out.getvalue()


async def test_an_unpaid_fee_blocks_submission_and_nothing_is_approved_automatically(
    client: httpx.AsyncClient, officer: dict, member: dict, admin_headers: dict
) -> None:
    await _published(client, officer, admin_headers, fee=5000)
    applied = (await client.post(MINE, json={"seat": "mca"}, headers=member)).json()
    aspirant = applied["application"]["id"]
    attached = await client.post(
        f"{MINE}documents/",
        data={"label": "National ID"},
        files={"file": ("id.png", _photo(), "image/png")},
        headers=member,
    )

    unpaid = await client.post(f"{MINE}submit/", json={"declaration": True}, headers=member)
    pushed = await client.post(
        f"/api/party/aspirants/{aspirant}/status/", json={"status": "submitted"}, headers=officer
    )
    paid = await client.post(
        f"/api/party/nominations/applications/{aspirant}/fee/",
        json={"reference": "QKX12AB34"},
        headers=officer,
    )
    submitted = await client.post(f"{MINE}submit/", json={"declaration": True}, headers=member)
    vetting = (await client.get(f"/api/party/aspirants/{aspirant}/", headers=officer)).json()
    document = vetting["documents"][0]
    download = await client.get(
        f"/api/party/nominations/applications/{aspirant}/documents/{document['id']}/",
        headers=officer,
    )

    assert attached.status_code == 201, attached.text
    assert unpaid.status_code == 400
    assert "KES 5,000" in unpaid.json()["detail"]
    assert pushed.status_code == 400
    assert paid.json()["fee_reference"] == "QKX12AB34"
    assert submitted.json()["application"]["status"] == "submitted"
    assert (vetting["status"], vetting["fee_kes"], vetting["declared_at"] is not None) == (
        "submitted",
        5000,
        True,
    )
    assert (document["label"], download.status_code) == ("National ID", 200)


async def test_an_officer_cannot_vet_their_own_application(
    client: httpx.AsyncClient, officer: dict, admin_headers: dict
) -> None:
    await _published(client, officer, admin_headers)
    applied = (await client.post(MINE, json={"seat": "mca"}, headers=officer)).json()
    aspirant = applied["application"]["id"]
    await client.post(f"{MINE}submit/", json={"declaration": True}, headers=officer)

    own = await client.post(
        f"/api/party/aspirants/{aspirant}/status/", json={"status": "approved"}, headers=officer
    )

    assert own.status_code == 403


async def test_a_members_application_walks_through_vetting_and_approval_to_a_workspace(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    officer: dict,
    member: dict,
    admin_headers: dict,
) -> None:
    await _published(client, officer, admin_headers)
    applied = await client.post(MINE, json={"seat": "mca"}, headers=member)
    aspirant = applied.json()["application"]["id"]
    status_url = f"/api/party/aspirants/{aspirant}/status/"
    workspace_url = f"/api/party/aspirants/{aspirant}/workspace/"
    logins = {"candidate": {"username": "mgombea"}, "manager": {"username": "mgombea-mgr"}}

    too_soon = await client.post(workspace_url, json=logins, headers=officer)
    submitted = await client.post(f"{MINE}submit/", json={"declaration": True}, headers=member)
    vetting = await client.get(f"/api/party/aspirants/{aspirant}/", headers=officer)
    approved = await client.post(status_url, json={"status": "approved"}, headers=officer)
    made = await client.post(workspace_url, json=logins, headers=officer)
    mine = await client.get(MINE, headers=member)

    assert too_soon.status_code == 400
    assert submitted.json()["application"]["status"] == "submitted"
    assert vetting.json()["status"] == "submitted"
    assert approved.json()["status"] == "approved"
    assert made.status_code == 201, made.text
    assert mine.json()["application"]["status"] == "approved"
    campaign = await session.get(Campaign, uuid.UUID(made.json()["aspirant"]["campaign_id"]))
    assert (campaign.seat, campaign.ward_id) == (Seat.MCA, world.ward.id)
    candidate = await session.scalar(select(User).where(User.username == "mgombea"))
    assert str(candidate.party_member_id) == vetting.json()["member"]["id"]
