"""The models: keys, deletes, constraints and computed values."""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Campaign,
    CampaignMember,
    CampaignMemberArea,
    Mobilizer,
    OfficeLevel,
    OperationalGrain,
    Post,
    PostKind,
    User,
    UserRole,
    VolunteerProfile,
)
from tests.factories import make_campaign, make_geography, make_rival_campaign


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


async def test_the_role_key_refuses_a_member_whose_role_differs_from_its_login(
    session: AsyncSession,
) -> None:
    _, _, ward, _ = await make_geography(session)
    campaign = await make_campaign(session, ward)
    coordinator = User(username="otieno", role=UserRole.COORDINATOR)
    session.add(coordinator)
    await session.flush()

    session.add(
        CampaignMember(campaign_id=campaign.id, user_id=coordinator.id, role=UserRole.COMMS)
    )
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.parametrize("role", [UserRole.CANDIDATE, UserRole.MANAGER])
async def test_a_campaign_has_one_candidate_and_one_manager(
    session: AsyncSession, role: UserRole
) -> None:
    _, _, ward, _ = await make_geography(session)
    campaign = await make_campaign(session, ward)
    first, second = User(username="first", role=role), User(username="second", role=role)
    session.add_all([first, second])
    await session.flush()
    if role is UserRole.MANAGER:
        session.add(CampaignMember(campaign_id=campaign.id, user_id=first.id, role=role))
        await session.commit()

    session.add(CampaignMember(campaign_id=campaign.id, user_id=second.id, role=role))
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.parametrize("places", ["both", "neither"])
async def test_an_area_row_holds_exactly_one_ward_or_centre(
    session: AsyncSession, places: str
) -> None:
    _, _, ward, centre = await make_geography(session)
    campaign = await make_campaign(session, ward)
    coordinator = User(username="otieno", role=UserRole.COORDINATOR)
    session.add(coordinator)
    await session.flush()
    member = CampaignMember(
        campaign_id=campaign.id, user_id=coordinator.id, role=UserRole.COORDINATOR
    )
    session.add(member)
    await session.flush()

    both = places == "both"
    session.add(
        CampaignMemberArea(
            campaign_member_id=member.id,
            ward_id=ward.id if both else None,
            registration_centre_id=centre.id if both else None,
        )
    )
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_a_pending_login_is_never_active(session: AsyncSession) -> None:
    session.add(User(username="wanjiru", role=UserRole.AGENT, pending=True, is_active=True))

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


@pytest.mark.parametrize(
    ("kind", "event_date"), [(PostKind.EVENT, None), (PostKind.NEWS, date(2026, 12, 1))]
)
async def test_only_an_event_has_a_date(
    session: AsyncSession, kind: PostKind, event_date: date | None
) -> None:
    session.add(Post(kind=kind, title="Rally in Nakuru", event_date=event_date))

    with pytest.raises(IntegrityError):
        await session.commit()


def _volunteer(ward_id, campaign: Campaign) -> VolunteerProfile:
    return VolunteerProfile(
        campaign_id=campaign.id,
        first_name="Wanjiru",
        last_name="Kamau",
        phone="+254712345678",
        ward_id=ward_id,
        preferred_contact="call",
        consent_wording="I agree.",
        consent_at=datetime.now(UTC),
    )


async def test_a_phone_volunteers_once_per_campaign(session: AsyncSession) -> None:
    _, _, ward, _ = await make_geography(session)
    campaigns = [await make_campaign(session, ward), await make_rival_campaign(session, ward)]
    session.add_all([_volunteer(ward.id, c) for c in campaigns])
    await session.commit()
    session.add(_volunteer(ward.id, campaigns[0]))

    with pytest.raises(IntegrityError):
        await session.commit()
