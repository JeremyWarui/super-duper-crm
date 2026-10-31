"""The models: keys, deletes, constraints and computed values."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Aspirant,
    AspirantStatus,
    Campaign,
    CampaignMember,
    Mobilizer,
    OfficeLevel,
    OperationalGrain,
    PartyRoleName,
    Seat,
    User,
    UserRole,
)
from tests.factories import make_campaign, make_geography, make_officer


async def test_ward_campaign_operates_at_centre_grain(session: AsyncSession) -> None:
    _, _, ward, _ = await make_geography(session)
    campaign = await make_campaign(session, ward, office_level=OfficeLevel.WARD)
    assert campaign.operational_grain is OperationalGrain.CENTRE


@pytest.mark.parametrize("office_level", [OfficeLevel.CONSTITUENCY, OfficeLevel.COUNTY])
async def test_higher_offices_operate_at_ward_grain(
    session: AsyncSession, office_level: OfficeLevel
) -> None:
    _, _, ward, _ = await make_geography(session)
    campaign = await make_campaign(session, ward, office_level=office_level)
    assert campaign.operational_grain is OperationalGrain.WARD


async def test_a_login_cannot_be_on_two_campaigns(session: AsyncSession) -> None:
    _, _, ward, _ = await make_geography(session)
    campaign = await make_campaign(session, ward)
    other = Campaign(title="Another", office_level=OfficeLevel.WARD, ward=ward)
    manager = User(username="amina", role=UserRole.MANAGER)
    session.add_all([other, manager])
    await session.flush()
    session.add(CampaignMember(campaign_id=campaign.id, user_id=manager.id, role=UserRole.MANAGER))
    await session.commit()

    session.add(CampaignMember(campaign_id=other.id, user_id=manager.id, role=UserRole.MANAGER))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_a_login_on_a_campaign_cannot_change_role(session: AsyncSession) -> None:
    _, _, ward, _ = await make_geography(session)
    campaign = await make_campaign(session, ward)
    manager = User(username="amina", role=UserRole.MANAGER)
    session.add(manager)
    await session.flush()
    session.add(CampaignMember(campaign_id=campaign.id, user_id=manager.id, role=UserRole.MANAGER))
    await session.commit()

    manager.role = UserRole.MOBILIZER
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_deleting_a_mobilizers_user_keeps_the_mobilizer(
    session: AsyncSession,
) -> None:
    _, _, ward, _ = await make_geography(session)
    campaign = await make_campaign(session, ward)
    user = User(username="juma", role=UserRole.MOBILIZER)
    mobilizer = Mobilizer(campaign=campaign, ward=ward, full_name="Juma", user=user)
    session.add(mobilizer)
    await session.commit()

    await session.delete(user)
    await session.commit()
    await session.refresh(mobilizer)
    assert mobilizer.user_id is None
    assert mobilizer.full_name == "Juma"


async def test_a_member_has_one_live_nomination_and_keeps_the_withdrawn_ones(
    session: AsyncSession,
) -> None:
    _, _, ward, _ = await make_geography(session)
    member_id = (
        await make_officer(session, ward, PartyRoleName.MEMBERSHIP_OFFICER)
    ).party_member_id
    nomination = {"member_id": member_id, "seat": Seat.MCA, "ward_id": ward.id}
    session.add(Aspirant(**nomination, status=AspirantStatus.WITHDRAWN))
    session.add(Aspirant(**nomination))
    await session.commit()

    session.add(Aspirant(**nomination, status=AspirantStatus.SUBMITTED))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_a_nomination_names_only_the_area_its_seat_is_fought_over(
    session: AsyncSession,
) -> None:
    _, constituency, ward, _ = await make_geography(session)
    member_id = (
        await make_officer(session, ward, PartyRoleName.MEMBERSHIP_OFFICER)
    ).party_member_id
    session.add(
        Aspirant(
            member_id=member_id, seat=Seat.MP, constituency_id=constituency.id, ward_id=ward.id
        )
    )

    with pytest.raises(IntegrityError):
        await session.commit()
