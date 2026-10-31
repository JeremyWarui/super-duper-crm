"""Volunteer profiles follow their member and are active only for approved members."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    ContactMethod,
    PartyConsentChannel,
    PartyMember,
    PartyMemberStatus,
    VolunteerProfile,
    VolunteerStatus,
)
from backend.services import membership, volunteers
from backend.services.consent import PARTY_WORDING, VOLUNTEER_WORDING
from backend.services.errors import Refused
from tests.conftest import World


async def make_volunteer(
    session: AsyncSession, world: World
) -> tuple[PartyMember, VolunteerProfile]:
    member = PartyMember(
        full_name="Wanjiru Kamau",
        phone="+254712345678",
        ward_id=world.ward.id,
        consent_wording=PARTY_WORDING[PartyConsentChannel.OFFICER_ENTRY],
        consent_channel=PartyConsentChannel.OFFICER_ENTRY,
        consent_at=datetime.now(UTC),
    )
    session.add(member)
    await session.flush()
    profile = VolunteerProfile(
        member_id=member.id,
        interests=["events"],
        preferred_contact=ContactMethod.CALL,
        consent_wording=VOLUNTEER_WORDING,
        consent_at=datetime.now(UTC),
    )
    session.add(profile)
    await session.commit()
    return member, profile


async def test_an_officer_cannot_activate_a_volunteer_until_the_member_is_approved(
    session: AsyncSession, world: World
):
    member, profile = await make_volunteer(session, world)

    with pytest.raises(Refused, match="approved member"):
        await volunteers.set_status(session, profile, VolunteerStatus.ACTIVE, actor=world.candidate)
    assert profile.status is VolunteerStatus.INTERESTED

    await membership.move(session, member, PartyMemberStatus.APPROVED, actor=world.candidate)
    await volunteers.set_status(session, profile, VolunteerStatus.ACTIVE, actor=world.candidate)
    assert profile.status is VolunteerStatus.ACTIVE


async def test_withdrawing_the_member_withdraws_the_profile(session: AsyncSession, world: World):
    member, profile = await make_volunteer(session, world)
    profile.withdraw_code = "volunteer-code"
    await session.commit()

    await membership.withdraw(session, member)
    await session.commit()

    await session.refresh(profile)
    assert profile.status is VolunteerStatus.WITHDRAWN
    assert profile.withdraw_code is None
