"""Branch officials: terms in office held by approved members, kept by the Membership Officer."""

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import PartyConsentChannel, PartyMember, PartyMemberStatus, PartyRoleName
from backend.services.consent import PARTY_WORDING
from tests.conftest import World
from tests.factories import auth, make_officer, sign_in

pytestmark = pytest.mark.party_only


async def member(
    session: AsyncSession, world: World, name: str, phone: str, status=PartyMemberStatus.APPROVED
) -> PartyMember:
    row = PartyMember(
        full_name=name,
        phone=phone,
        ward_id=world.ward.id,
        status=status,
        consent_wording=PARTY_WORDING[PartyConsentChannel.OFFICER_ENTRY],
        consent_channel=PartyConsentChannel.OFFICER_ENTRY,
        consent_at=datetime.now(UTC),
    )
    session.add(row)
    await session.commit()
    return row


@pytest.fixture
async def officer(session: AsyncSession, client: httpx.AsyncClient, world: World) -> dict:
    await make_officer(session, world.ward, PartyRoleName.MEMBERSHIP_OFFICER)
    return auth(await sign_in(client, "ofisa"))


async def listing(client, world: World, headers: dict) -> dict:
    path = f"/api/party/office/branches/{world.county.id}/officials/"
    return (await client.get(path, headers=headers)).json()


def appoint(client, headers, world: World, who: PartyMember, start: str, office: str = "chair"):
    return client.post(
        f"/api/party/office/branches/{world.county.id}/officials/",
        json={"office": office, "member": str(who.id), "term_start": start},
        headers=headers,
    )


async def test_only_an_approved_member_holds_an_office(
    client: httpx.AsyncClient, session: AsyncSession, world: World, officer: dict
) -> None:
    pending = await member(
        session, world, "Pending Person", "+254711000001", PartyMemberStatus.PENDING
    )
    approved = await member(session, world, "Wanjiru Kamau", "+254711000002")

    refused = await appoint(client, officer, world, pending, "2026-10-01")
    taken = await appoint(client, officer, world, approved, "2026-10-01")

    assert refused.status_code == 400
    assert "approved party member" in refused.json()["detail"]
    assert taken.status_code == 201, taken.text
    assert (taken.json()["holder_name"], taken.json()["label"]) == ("Wanjiru Kamau", "Chairperson")


async def test_an_office_has_one_current_holder_and_the_old_term_moves_to_history(
    client: httpx.AsyncClient, session: AsyncSession, world: World, officer: dict
) -> None:
    first = await member(session, world, "Wanjiru Kamau", "+254711000002")
    second = await member(session, world, "Otieno Ouma", "+254711000003")
    await appoint(client, officer, world, first, "2026-01-01")

    replaced = await appoint(client, officer, world, second, "2026-10-15")
    earlier = await appoint(client, officer, world, first, "2026-10-15")
    listed = await listing(client, world, officer)

    assert replaced.status_code == 201
    assert earlier.status_code == 400
    assert [o["holder_name"] for o in listed["current"]] == ["Otieno Ouma"]
    assert [(o["holder_name"], o["term_end"], o["end_reason"]) for o in listed["history"]] == [
        ("Wanjiru Kamau", "2026-10-14", "replaced")
    ]


async def test_an_ended_term_leaves_the_office_vacant(
    client: httpx.AsyncClient, session: AsyncSession, world: World, officer: dict
) -> None:
    holder = await member(session, world, "Wanjiru Kamau", "+254711000002")
    term = (await appoint(client, officer, world, holder, "2026-01-01")).json()

    ended = await client.post(
        f"/api/party/office/officials/{term['id']}/end/",
        json={"term_end": "2026-10-31", "end_reason": "resigned"},
        headers=officer,
    )
    listed = await listing(client, world, officer)

    assert ended.status_code == 200, ended.text
    assert listed["current"] == []
    assert [o["end_reason"] for o in listed["history"]] == ["resigned"]


async def test_the_public_page_names_only_the_officials_in_office(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    officer: dict,
    admin_headers: dict,
) -> None:
    old = await member(session, world, "Former Chair", "+254711000004")
    now = await member(session, world, "Wanjiru Kamau", "+254711000002")
    soon = await member(session, world, "Next Secretary", "+254711000005")
    await appoint(client, officer, world, old, "2025-01-01")
    await appoint(client, officer, world, now, "2026-06-01")
    await appoint(client, officer, world, soon, "2027-01-01", office="secretary")
    await client.put(
        f"/api/admin/party/branches/{world.county.id}/",
        json={"published": True},
        headers=admin_headers,
    )

    shown = (await client.get(f"/api/party/branches/{world.county.id}/")).json()

    assert shown["officials"] == [
        {"office": "chair", "label": "Chairperson", "name": "Wanjiru Kamau"}
    ]


async def test_a_campaign_manager_cannot_change_officials(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    holder = await member(session, world, "Wanjiru Kamau", "+254711000002")

    answer = await appoint(client, world.headers("manager"), world, holder, "2026-10-01")

    assert answer.status_code == 403


async def test_a_holder_whose_membership_lapses_is_no_longer_named(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    officer: dict,
    admin_headers: dict,
) -> None:
    holder = await member(session, world, "Wanjiru Kamau", "+254711000002")
    await appoint(client, officer, world, holder, "2026-01-01")
    await client.put(
        f"/api/admin/party/branches/{world.county.id}/",
        json={"published": True},
        headers=admin_headers,
    )
    holder.status = PartyMemberStatus.WITHDRAWN
    await session.commit()

    shown = (await client.get(f"/api/party/branches/{world.county.id}/")).json()
    listed = await listing(client, world, officer)

    assert shown["officials"] == []
    assert [(o["holder_name"], o["lapsed"]) for o in listed["current"]] == [("Wanjiru Kamau", True)]
