"""The models: keys, deletes, constraints and computed values."""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    Base,
    Campaign,
    CampaignMember,
    Constituency,
    County,
    Event,
    EventStatus,
    Mobilizer,
    OfficeLevel,
    OperationalGrain,
    RegistrationCentre,
    Supporter,
    SupportLevel,
    Target,
    User,
    UserRole,
    Ward,
)
from tests.factories import make_campaign, make_geography, make_mobilizer

EXPECTED_TABLES = {
    "users",
    "auth_tokens",
    "counties",
    "constituencies",
    "wards",
    "registration_centres",
    "campaign_members",
    "campaigns",
    "targets",
    "mobilizers",
    "events",
    "supporters",
}


def test_metadata_matches_the_mapped_classes() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


async def test_primary_keys_are_uuids_generated_before_flush(session: AsyncSession) -> None:
    county = County(name="Kisumu")
    assert isinstance(county.id, uuid.UUID), "id must exist before the flush"
    generated = county.id
    session.add(county)
    await session.commit()
    assert county.id == generated, "the database must not overwrite the client id"


async def test_deleting_a_county_cascades_to_constituencies_and_wards(
    session: AsyncSession,
) -> None:
    county, _, _, _ = await make_geography(session)
    await session.delete(county)
    await session.commit()

    assert (await session.execute(select(Constituency))).scalars().all() == []
    assert (await session.execute(select(Ward))).scalars().all() == []
    assert (await session.execute(select(RegistrationCentre))).scalars().all() == []


async def test_negative_registered_voters_is_rejected(session: AsyncSession) -> None:
    session.add(County(name="Bad", registered_voters=-1))
    with pytest.raises(IntegrityError):
        await session.commit()


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


async def test_area_returns_the_unit_named_by_the_office_level(
    session: AsyncSession,
) -> None:
    _, constituency, ward, _ = await make_geography(session)
    campaign = await make_campaign(session, ward, office_level=OfficeLevel.WARD)
    campaign.constituency = constituency
    await session.commit()

    loaded = (
        await session.execute(
            select(Campaign)
            .options(selectinload(Campaign.ward), selectinload(Campaign.constituency))
            .where(Campaign.id == campaign.id)
        )
    ).scalar_one()
    assert loaded.area is not None
    assert loaded.area.id == ward.id

    loaded.office_level = OfficeLevel.CONSTITUENCY
    assert loaded.area.id == constituency.id


async def test_area_names_the_missing_eager_load_instead_of_lazy_loading(
    session: AsyncSession,
) -> None:
    _, _, ward, _ = await make_geography(session)
    campaign = await make_campaign(session, ward)
    session.expunge_all()

    unloaded = (
        await session.execute(select(Campaign).where(Campaign.id == campaign.id))
    ).scalar_one()
    with pytest.raises(RuntimeError, match="selectinload"):
        _ = unloaded.area


async def test_deleting_a_ward_nulls_the_campaign_but_keeps_it(
    session: AsyncSession,
) -> None:
    _, _, ward, _ = await make_geography(session)
    campaign = await make_campaign(session, ward)
    await session.delete(ward)
    await session.commit()
    await session.refresh(campaign)
    assert campaign.ward_id is None


async def test_a_campaign_s_candidate_is_the_member_whose_place_is_candidate(
    session: AsyncSession,
) -> None:
    _, _, ward, _ = await make_geography(session)
    campaign = await make_campaign(session, ward)

    loaded = await session.scalar(
        select(Campaign).where(Campaign.id == campaign.id).options(selectinload(Campaign.candidate))
    )

    assert loaded.candidate is not None
    assert loaded.candidate.username == f"candidate-{ward.code}"


async def test_a_campaign_cannot_hold_a_second_candidate(session: AsyncSession) -> None:
    _, _, ward, _ = await make_geography(session)
    campaign = await make_campaign(session, ward)
    other = User(username="second-candidate", role=UserRole.CANDIDATE)
    session.add(other)
    await session.flush()

    session.add(CampaignMember(campaign_id=campaign.id, user_id=other.id, role=UserRole.CANDIDATE))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_a_campaign_may_hold_many_managers(session: AsyncSession) -> None:
    _, _, ward, _ = await make_geography(session)
    campaign = await make_campaign(session, ward)
    for name in ("amina", "otieno"):
        manager = User(username=name, role=UserRole.MANAGER)
        session.add(manager)
        await session.flush()
        session.add(
            CampaignMember(campaign_id=campaign.id, user_id=manager.id, role=UserRole.MANAGER)
        )
    await session.commit()

    managers = await session.scalar(
        select(func.count())
        .select_from(CampaignMember)
        .where(CampaignMember.campaign_id == campaign.id, CampaignMember.role == UserRole.MANAGER)
    )
    assert managers == 2


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


async def test_deleting_the_candidate_takes_their_place_and_leaves_the_campaign(
    session: AsyncSession,
) -> None:
    _, _, ward, _ = await make_geography(session)
    campaign_id = (await make_campaign(session, ward)).id
    loaded = await session.scalar(
        select(Campaign).where(Campaign.id == campaign_id).options(selectinload(Campaign.candidate))
    )

    await session.delete(loaded.candidate)
    await session.commit()
    session.expire_all()

    left = await session.scalar(
        select(Campaign).where(Campaign.id == campaign_id).options(selectinload(Campaign.candidate))
    )
    assert left is not None
    assert left.candidate is None


async def test_one_ward_level_target_per_campaign_and_ward(session: AsyncSession) -> None:
    _, _, ward, _ = await make_geography(session)
    campaign = await make_campaign(session, ward)
    session.add(Target(campaign=campaign, ward=ward))
    await session.commit()

    session.add(Target(campaign=campaign, ward=ward))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_one_centre_level_target_per_campaign_and_centre(
    session: AsyncSession,
) -> None:
    _, _, ward, centre = await make_geography(session)
    campaign = await make_campaign(session, ward)
    session.add(Target(campaign=campaign, ward=ward, registration_centre=centre))
    await session.commit()

    session.add(Target(campaign=campaign, ward=ward, registration_centre=centre))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_centre_targets_do_not_collide_with_the_ward_target(
    session: AsyncSession,
) -> None:
    _, _, ward, centre = await make_geography(session)
    campaign = await make_campaign(session, ward)
    other_centre = RegistrationCentre(ward=ward, name="Aga Khan Hall", registered_voters=1_500)
    session.add_all(
        [
            other_centre,
            Target(campaign=campaign, ward=ward),
            Target(campaign=campaign, ward=ward, registration_centre=centre),
        ]
    )
    await session.commit()
    session.add(Target(campaign=campaign, ward=ward, registration_centre=other_centre))
    await session.commit()

    targets = (await session.execute(select(Target))).scalars().all()
    assert len(targets) == 3


async def test_ward_target_counts_the_whole_ward_roll(session: AsyncSession) -> None:
    _, _, ward, _ = await make_geography(session, ward_voters=10_000)
    campaign = await make_campaign(session, ward)
    target = Target(campaign=campaign, ward=ward, projected_turnout_pct=Decimal("65.00"))
    session.add(target)
    await session.commit()

    loaded = (
        await session.execute(
            select(Target)
            .options(selectinload(Target.ward), selectinload(Target.registration_centre))
            .where(Target.id == target.id)
        )
    ).scalar_one()
    assert loaded.registered_voters == 10_000
    assert loaded.recompute_win_number() == 3_251


async def test_centre_target_counts_only_that_centre(session: AsyncSession) -> None:
    _, _, ward, centre = await make_geography(session, ward_voters=10_000)
    campaign = await make_campaign(session, ward)
    target = Target(
        campaign=campaign,
        ward=ward,
        registration_centre=centre,
        projected_turnout_pct=Decimal("65.00"),
    )
    session.add(target)
    await session.commit()

    loaded = (
        await session.execute(
            select(Target)
            .options(selectinload(Target.ward), selectinload(Target.registration_centre))
            .where(Target.id == target.id)
        )
    ).scalar_one()
    assert loaded.registered_voters == 2_000, "must not fall back to the ward roll"
    assert loaded.recompute_win_number() == 651


async def test_recompute_win_number_persists_through_the_session(
    session: AsyncSession,
) -> None:
    _, _, ward, _ = await make_geography(session, ward_voters=10_000)
    campaign = await make_campaign(session, ward)
    target = Target(campaign=campaign, ward=ward, projected_turnout_pct=Decimal("65.00"))
    session.add(target)
    await session.commit()

    loaded = (
        await session.execute(
            select(Target)
            .options(selectinload(Target.ward), selectinload(Target.registration_centre))
            .where(Target.id == target.id)
        )
    ).scalar_one()
    loaded.recompute_win_number()
    await session.commit()

    session.expunge_all()
    reread = await session.get(Target, target.id)
    assert reread is not None
    assert reread.votes_needed == 3_251


@pytest.mark.parametrize(
    ("needed", "committed", "remaining", "progress"),
    [
        (100, 0, 100, 0.0),
        (100, 40, 60, 40.0),
        (100, 100, 0, 100.0),
        (100, 150, 0, 150.0),
        (3, 1, 2, 33.3),
        (None, 25, None, 0.0),
        (0, 25, 0, 0.0),
    ],
)
def test_target_progress_arithmetic(
    needed: int | None, committed: int, remaining: int | None, progress: float
) -> None:
    target = Target(votes_needed=needed, votes_committed=committed)
    assert target.votes_remaining == remaining
    assert target.progress_pct == progress


async def test_target_rejects_negative_committed_votes(session: AsyncSession) -> None:
    _, _, ward, _ = await make_geography(session)
    campaign = await make_campaign(session, ward)
    session.add(Target(campaign=campaign, ward=ward, votes_committed=-5))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_target_rejects_turnout_above_one_hundred_percent(
    session: AsyncSession,
) -> None:
    _, _, ward, _ = await make_geography(session)
    campaign = await make_campaign(session, ward)
    session.add(Target(campaign=campaign, ward=ward, projected_turnout_pct=Decimal("120.00")))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_a_user_holds_at_most_one_mobilizer_profile(session: AsyncSession) -> None:
    _, _, ward, _ = await make_geography(session)
    campaign = await make_campaign(session, ward)
    user = User(username="juma", role=UserRole.MOBILIZER)
    session.add(Mobilizer(campaign=campaign, ward=ward, full_name="Juma", user=user))
    await session.commit()

    session.add(Mobilizer(campaign=campaign, ward=ward, full_name="Juma again", user_id=user.id))
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
    ("reached", "attended", "expected"),
    [(0, 0, 0.0), (0, 10, 0.0), (200, 150, 75.0), (3, 1, 33.3), (100, 120, 120.0)],
)
def test_event_turnout_pct(reached: int, attended: int, expected: float) -> None:
    event = Event(number_reached=reached, number_attended=attended)
    assert event.turnout_pct == expected


async def test_event_defaults_to_planned(session: AsyncSession) -> None:
    _, _, ward, _ = await make_geography(session)
    campaign = await make_campaign(session, ward)
    event = Event(campaign=campaign, ward=ward, title="Parklands rally")
    session.add(event)
    await session.commit()
    assert event.status is EventStatus.PLANNED
    assert event.number_reached == 0


async def test_deleting_a_mobilizer_keeps_their_events(session: AsyncSession) -> None:
    _, _, ward, _ = await make_geography(session)
    campaign = await make_campaign(session, ward)
    mobilizer = await make_mobilizer(session, campaign, ward)
    event = Event(campaign=campaign, ward=ward, mobilizer=mobilizer, title="Rally")
    session.add(event)
    await session.commit()

    await session.delete(mobilizer)
    await session.commit()
    await session.refresh(event)
    assert event.mobilizer_id is None


async def test_supporter_defaults_to_undecided_without_consent(
    session: AsyncSession,
) -> None:
    _, _, ward, _ = await make_geography(session)
    campaign = await make_campaign(session, ward)
    supporter = Supporter(campaign=campaign, ward=ward, full_name="Wanjiku N.")
    session.add(supporter)
    await session.commit()
    assert supporter.support_level is SupportLevel.UNDECIDED
    assert supporter.consent_given is False
    assert supporter.created_at is not None


def test_enum_values_and_labels() -> None:
    assert [(m.value, m.label) for m in UserRole] == [
        ("candidate", "Candidate"),
        ("manager", "Campaign Manager"),
        ("mobilizer", "Mobilizer"),
    ]
    assert [(m.value, m.label) for m in OfficeLevel] == [
        ("ward", "Ward (MCA)"),
        ("constituency", "Constituency (MP)"),
        ("county", "County (Governor / Senator / Women Rep)"),
    ]
    assert [(m.value, m.label) for m in EventStatus] == [
        ("planned", "Planned"),
        ("done", "Done"),
        ("cancelled", "Cancelled"),
    ]
    assert [(m.value, m.label) for m in SupportLevel] == [
        ("supporter", "Supporter"),
        ("undecided", "Undecided"),
        ("opposed", "Opposed"),
    ]


def test_enum_members_serialize_as_their_plain_string_value() -> None:
    assert UserRole.MANAGER == "manager"
    assert f"{EventStatus.DONE}" == "done"


async def test_user_defaults_to_manager(session: AsyncSession) -> None:
    user = User(username="asha", first_name="Asha", last_name="Mwangi")
    session.add(user)
    await session.commit()
    assert user.role is UserRole.MANAGER
    assert str(user) == "Asha Mwangi (Campaign Manager)"


async def test_the_orm_rejects_an_unknown_role(session: AsyncSession) -> None:
    session.add(User(username="bad", role="dictator"))
    with pytest.raises(StatementError):
        await session.commit()


async def test_the_database_rejects_an_unknown_role(session: AsyncSession) -> None:
    statement = text(
        "INSERT INTO users (id, username, email, first_name, last_name, phone, "
        "role, password_hash, is_active, is_superuser, created_at) VALUES "
        "(:id, 'bad', '', '', '', '', 'dictator', '', 1, 0, CURRENT_TIMESTAMP)"
    )
    with pytest.raises(IntegrityError, match="CHECK constraint failed"):
        await session.execute(statement, {"id": uuid.uuid4().hex})
        await session.commit()
