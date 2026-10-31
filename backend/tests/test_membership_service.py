"""The party register: the move table is enforced and a phone is on it once."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import PartyConsentChannel, PartyMember, PartyMemberStatus
from backend.services import membership
from backend.services.consent import PARTY_WORDING
from backend.services.errors import Refused
from tests.conftest import World


def make_member(world: World, *, full_name: str = "Wanjiru Kamau") -> PartyMember:
    return PartyMember(
        full_name=full_name,
        phone="+254712345678",
        ward_id=world.ward.id,
        consent_wording=PARTY_WORDING[PartyConsentChannel.OFFICER_ENTRY],
        consent_channel=PartyConsentChannel.OFFICER_ENTRY,
        consent_at=datetime.now(UTC),
    )


async def test_a_pending_member_cannot_be_suspended(session: AsyncSession, world: World):
    member = make_member(world)
    session.add(member)
    await session.commit()

    with pytest.raises(Refused, match="pending member cannot be moved to suspended"):
        await membership.move(session, member, PartyMemberStatus.SUSPENDED, actor=world.candidate)
    assert member.status is PartyMemberStatus.PENDING


async def test_the_database_refuses_a_second_member_with_the_same_phone(
    session: AsyncSession, world: World
):
    session.add(make_member(world))
    await session.commit()
    session.add(make_member(world, full_name="Someone Else"))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_a_move_on_a_stale_read_is_refused_and_leaves_the_other_move_standing(
    session: AsyncSession, world: World
):
    member = make_member(world)
    session.add(member)
    await session.commit()
    await session.execute(
        update(PartyMember)
        .where(PartyMember.id == member.id)
        .values(status=PartyMemberStatus.APPROVED)
        .execution_options(synchronize_session=False)
    )

    with pytest.raises(Refused, match="changed meanwhile"):
        await membership.move(session, member, PartyMemberStatus.REJECTED, actor=world.candidate)
    stored = await session.scalar(select(PartyMember.status).where(PartyMember.id == member.id))
    assert stored is PartyMemberStatus.APPROVED
