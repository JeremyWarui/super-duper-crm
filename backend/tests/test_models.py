"""The models: keys, deletes, constraints and computed values."""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Aspirant,
    AspirantStatus,
    Campaign,
    CampaignMember,
    CampaignSubscription,
    CrmPlan,
    EntryKind,
    Mobilizer,
    OfficeLevel,
    OperationalGrain,
    PartyPost,
    PartyRoleName,
    PostKind,
    ReceiptMethod,
    Seat,
    SubscriptionEntry,
    User,
    UserRole,
    VolunteerProfile,
)
from tests.factories import make_campaign, make_geography, make_officer, make_rival_campaign


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


async def _plan_and_subscription(session: AsyncSession):
    _, _, ward, _ = await make_geography(session)
    campaign = await make_campaign(session, ward)
    plan = CrmPlan(name="Ward season", price_kes=5_000, duration_days=30)
    session.add(plan)
    await session.flush()
    return plan, campaign.subscription


def _payment(subscription_id, plan_id, **fields):
    values = {
        "subscription_id": subscription_id,
        "kind": EntryKind.PAYMENT,
        "plan_id": plan_id,
        "amount_kes": 5_000,
        "method": ReceiptMethod.MPESA,
        "reference": "SK41AB12CD",
        "received_on": date(2026, 11, 1),
        "days": 30,
        "paid_until_after": date(2026, 11, 30),
    }
    return SubscriptionEntry(**(values | fields))


async def test_a_new_campaign_has_an_unpaid_subscription(session: AsyncSession) -> None:
    _, _, ward, _ = await make_geography(session)
    campaign = Campaign(title="Githurai MCA 2027", office_level=OfficeLevel.WARD, ward=ward)
    session.add(campaign)
    await session.commit()

    stored = await session.scalar(
        select(CampaignSubscription).where(CampaignSubscription.campaign_id == campaign.id)
    )

    assert stored is not None
    assert stored.paid_until is None


async def test_a_payment_needs_its_reference(session: AsyncSession) -> None:
    plan, subscription = await _plan_and_subscription(session)
    session.add(_payment(subscription.id, plan.id, reference=None))

    with pytest.raises(IntegrityError):
        await session.commit()


async def test_a_reference_is_recorded_once_until_that_payment_is_voided(
    session: AsyncSession,
) -> None:
    plan, subscription = await _plan_and_subscription(session)
    ids = (subscription.id, plan.id)
    first = _payment(*ids)
    session.add(first)
    await session.commit()
    first_id = first.id

    session.add(_payment(*ids))
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()

    await session.execute(
        update(SubscriptionEntry)
        .where(SubscriptionEntry.id == first_id)
        .values(voided_at=datetime.now(UTC), void_reason="Entered against the wrong campaign.")
    )
    session.add(_payment(*ids))
    await session.commit()


@pytest.mark.parametrize(
    ("kind", "event_date"), [(PostKind.EVENT, None), (PostKind.NEWS, date(2026, 12, 1))]
)
async def test_only_an_event_has_a_date(
    session: AsyncSession, kind: PostKind, event_date: date | None
) -> None:
    session.add(PartyPost(kind=kind, title="Rally in Nakuru", event_date=event_date))

    with pytest.raises(IntegrityError):
        await session.commit()


async def test_a_phone_volunteers_once_for_the_party_and_once_per_campaign(
    session: AsyncSession,
) -> None:
    _, _, ward, _ = await make_geography(session)
    campaigns = [await make_campaign(session, ward), await make_rival_campaign(session, ward)]

    def volunteer(campaign: Campaign | None) -> VolunteerProfile:
        return VolunteerProfile(
            campaign_id=campaign.id if campaign else None,
            first_name="Wanjiru",
            last_name="Kamau",
            phone="+254712345678",
            ward_id=ward.id,
            preferred_contact="call",
            consent_wording="I agree.",
            consent_at=datetime.now(UTC),
        )

    session.add_all([volunteer(None), *(volunteer(c) for c in campaigns)])
    await session.commit()
    session.add(volunteer(None))

    with pytest.raises(IntegrityError):
        await session.commit()
