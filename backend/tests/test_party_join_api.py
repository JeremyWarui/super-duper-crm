"""The public party application and withdrawal."""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AuditEvent, PartyMember, PartyMemberStatus, PartyRequest
from backend.services.membership import process_requests
from tests.conftest import World


def _application(world: World, **overrides) -> dict:
    return {
        "full_name": "Wanjiru Kamau",
        "phone": "0712 345678",
        "ward": str(world.ward.id),
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
        "/api/party/join/", json=_application(world, full_name="Someone Else")
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
