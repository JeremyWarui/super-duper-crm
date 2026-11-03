"""The inbox's work never depends on what the register holds.

Every public request of one shape must send the same SQL whatever the member's status, whether
they volunteer, and whether the code is live, spent or unknown. A difference is a timing signal a
public caller can average out of the server's latency.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from backend.models import (
    Aspirant,
    AspirantStatus,
    ContactMethod,
    PartyConsentChannel,
    PartyMember,
    PartyMemberStatus,
    Seat,
    VolunteerProfile,
    VolunteerStatus,
)
from backend.services import membership
from backend.services.aspirants import LIVE
from backend.services.consent import PARTY_WORDING, VOLUNTEER_WORDING
from tests.conftest import World

PHONE = "+254712345678"
STRANGER = "+254799000111"
MEMBER_STATES = [None, *PartyMemberStatus]
VOLUNTEER_STATES = [None, *VolunteerStatus]
VOLUNTEER_PART = {"interests": ["events"], "preferred_contact": "call"}


async def _register(
    session: AsyncSession,
    world: World,
    member_status: PartyMemberStatus | None,
    volunteer_status: VolunteerStatus | None,
) -> None:
    if member_status is None:
        return
    member = PartyMember(
        full_name="Wanjiru Kamau",
        phone=PHONE,
        ward_id=world.ward.id,
        status=member_status,
        consent_wording=PARTY_WORDING[PartyConsentChannel.OFFICER_ENTRY],
        consent_channel=PartyConsentChannel.OFFICER_ENTRY,
        consent_at=datetime.now(UTC),
        withdraw_code=None if member_status is PartyMemberStatus.WITHDRAWN else "member-code",
    )
    session.add(member)
    await session.flush()
    if volunteer_status is not None:
        session.add(
            VolunteerProfile(
                member_id=member.id,
                first_name="Wanjiru",
                last_name="Kamau",
                phone=PHONE,
                ward_id=world.ward.id,
                status=volunteer_status,
                interests=["events"],
                preferred_contact=ContactMethod.CALL,
                consent_wording=VOLUNTEER_WORDING,
                consent_at=datetime.now(UTC),
                withdraw_code=None if volunteer_status is VolunteerStatus.WITHDRAWN else "v-code",
            )
        )
    await session.commit()


async def _sent(engine: AsyncEngine, session: AsyncSession) -> tuple[str, ...]:
    sent: list[str] = []

    def keep(_conn, _cursor, statement, *_args):  # type: ignore[no-untyped-def]
        sent.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", keep)
    try:
        await membership.process_requests(session)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", keep)
    return tuple(sent)


def _queue(session: AsyncSession, world: World, shape: str) -> None:
    if shape.startswith("join"):
        membership.request_join(
            session,
            full_name="Achieng",
            phone=STRANGER if shape.endswith("stranger") else PHONE,
            email=None,
            ward_id=world.ward.id,
            volunteer=VOLUNTEER_PART if "volunteer" in shape else None,
        )
    elif shape == "withdraw live":
        membership.request_withdraw(session, "member-code")
    elif shape == "withdraw unknown":
        membership.request_withdraw(session, "no-such-code")
    elif shape == "volunteer withdraw live":
        membership.request_volunteer_withdraw(session, "v-code")
    else:
        membership.request_volunteer_withdraw(session, "no-such-code")


# Each shape's variants must match: the registered number against a stranger's, and a live code
# against an unknown one.
SHAPES = {
    "join": ["join", "join stranger"],
    "join+volunteer": ["join+volunteer", "join+volunteer stranger"],
    "withdraw": ["withdraw live", "withdraw unknown"],
    "volunteer withdraw": ["volunteer withdraw live", "volunteer withdraw unknown"],
}


@pytest.mark.parametrize("shape", sorted(SHAPES))
@pytest.mark.parametrize("member_status", MEMBER_STATES, ids=str)
@pytest.mark.parametrize("volunteer_status", VOLUNTEER_STATES, ids=str)
async def test_one_request_shape_sends_one_statement_list(
    engine: AsyncEngine,
    session: AsyncSession,
    world: World,
    shape: str,
    member_status: PartyMemberStatus | None,
    volunteer_status: VolunteerStatus | None,
) -> None:
    if member_status is None and volunteer_status is not None:
        pytest.skip("a profile needs a member")
    await _register(session, world, member_status, volunteer_status)
    sent = set()
    for variant in SHAPES[shape]:
        _queue(session, world, variant)
        await session.commit()
        sent.add(await _sent(engine, session))

    assert len(sent) == 1


ASPIRANT_STATES = [None, *sorted(LIVE)]
# A live nomination exists only for an approved or suspended member, and a suspended member's
# approved nomination is suspended with them.
NOMINATED = (PartyMemberStatus.APPROVED, PartyMemberStatus.SUSPENDED)


@pytest.mark.parametrize("member_status", NOMINATED, ids=str)
@pytest.mark.parametrize("aspirant_status", ASPIRANT_STATES, ids=str)
async def test_a_withdrawal_sends_one_statement_list_whatever_the_nomination(
    engine: AsyncEngine,
    session: AsyncSession,
    world: World,
    member_status: PartyMemberStatus,
    aspirant_status: AspirantStatus | None,
) -> None:
    if (member_status, aspirant_status) == (PartyMemberStatus.SUSPENDED, AspirantStatus.APPROVED):
        pytest.skip("a suspended member's approved nomination is suspended")
    await _register(session, world, member_status, None)
    if aspirant_status is not None:
        member_id = await session.scalar(select(PartyMember.id).where(PartyMember.phone == PHONE))
        session.add(
            Aspirant(
                member_id=member_id, seat=Seat.MCA, ward_id=world.ward.id, status=aspirant_status
            )
        )
        await session.commit()
    sent = set()
    for variant in SHAPES["withdraw"]:
        _queue(session, world, variant)
        await session.commit()
        sent.add(await _sent(engine, session))

    assert len(sent) == 1
