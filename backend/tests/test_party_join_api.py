"""The public party application and withdrawal."""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import PartyMember, PartyMemberStatus
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
    member = await session.scalar(select(PartyMember))
    member.status = PartyMemberStatus.APPROVED
    await session.commit()
    code = member.withdraw_code

    repeat = await client.post(
        "/api/party/join/", json=_application(world, full_name="Someone Else")
    )
    await session.refresh(member)

    assert (repeat.status_code, set(repeat.json())) == (new.status_code, set(new.json()))
    assert repeat.json()["withdraw_url"].startswith("/party/withdraw/")
    assert repeat.json()["withdraw_url"] != new.json()["withdraw_url"]
    assert (member.full_name, member.status, member.withdraw_code) == (
        "Wanjiru Kamau",
        PartyMemberStatus.APPROVED,
        code,
    )
