"""The party register: the move table is enforced and a phone is on it once."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import event, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from backend.models import (
    PartyConsentChannel,
    PartyMember,
    PartyMemberStatus,
    PartyRequest,
    PartyRequestKind,
)
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


async def test_a_join_for_an_approved_member_leaves_them_approved_and_unchanged(
    session: AsyncSession, world: World
):
    member = make_member(world)
    member.status = PartyMemberStatus.APPROVED
    session.add(member)
    await session.commit()
    membership.request_join(
        session, full_name="Someone Else", phone=member.phone, email=None, ward_id=world.ward.id
    )
    await session.commit()

    await membership.process_requests(session)
    await session.refresh(member)

    assert (member.status, member.full_name) == (PartyMemberStatus.APPROVED, "Wanjiru Kamau")


async def test_a_request_that_cannot_be_applied_is_dropped_and_the_queue_moves_on(
    session: AsyncSession, world: World
):
    session.add(
        PartyRequest(
            kind=PartyRequestKind.JOIN,
            code="broken",
            payload={"phone": "+254700000009", "ward_id": "not-a-uuid"},
        )
    )
    await session.commit()
    membership.request_join(
        session,
        full_name="Achieng Otieno",
        phone="+254711222333",
        email=None,
        ward_id=world.ward.id,
    )
    await session.commit()

    taken = await membership.process_requests(session)
    phones = (await session.scalars(select(PartyMember.phone))).all()

    assert taken == 2
    assert phones == ["+254711222333"]
    assert (await session.scalars(select(PartyRequest))).all() == []


async def _statements(engine: AsyncEngine, session: AsyncSession) -> list[str]:
    """The SQL the next inbox run sends, in order."""
    sent: list[str] = []

    def keep(_conn, _cursor, statement, *_args):  # type: ignore[no-untyped-def]
        sent.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", keep)
    try:
        await membership.process_requests(session)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", keep)
    return sent


async def test_the_inbox_runs_the_same_statements_whether_or_not_the_phone_is_registered(
    engine: AsyncEngine, session: AsyncSession, world: World
):
    member = make_member(world)
    member.status = PartyMemberStatus.APPROVED
    session.add(member)
    await session.commit()
    runs = []
    for phone in (member.phone, "+254799000111"):
        code, _ = membership.request_join(
            session, full_name="Achieng Otieno", phone=phone, email=None, ward_id=world.ward.id
        )
        membership.request_withdraw(session, code)
        await session.commit()
        runs.append(await _statements(engine, session))

    assert runs[0] == runs[1]
