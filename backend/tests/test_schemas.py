"""Read schemas: they validate off a mapped instance, and they leak nothing."""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Event,
    EventStatus,
    OfficeLevel,
    OperationalGrain,
    PollingStation,
    Supporter,
    Target,
    User,
    UserRole,
)
from backend.schemas import (
    CampaignRead,
    ConstituencyRead,
    CountyRead,
    EventRead,
    MobilizerRead,
    PollingStationRead,
    RegistrationCentreRead,
    SupporterRead,
    TargetRead,
    UserRead,
    WardRead,
)
from tests.factories import make_campaign, make_geography, make_mobilizer


async def test_user_read_never_carries_the_password_hash(session: AsyncSession) -> None:
    user = User(
        username="asha",
        first_name="Asha",
        last_name="Mwangi",
        role=UserRole.CANDIDATE,
        password_hash="argon2$do-not-serialize-me",
        is_superuser=True,
    )
    session.add(user)
    await session.commit()  # column defaults only fire on INSERT

    schema = UserRead.model_validate(user)
    dumped = schema.model_dump()

    assert "password_hash" not in dumped
    assert "is_superuser" not in dumped
    assert "do-not-serialize-me" not in schema.model_dump_json()
    assert dumped["full_name"] == "Asha Mwangi"
    assert dumped["role"] is UserRole.CANDIDATE


def test_user_read_rejects_an_unexpected_field() -> None:
    """`extra="forbid"` is what stops a stray key from being accepted silently."""
    with pytest.raises(ValueError, match="password_hash"):
        UserRead(
            id="00000000-0000-0000-0000-000000000001",
            username="asha",
            email="",
            first_name="Asha",
            last_name="Mwangi",
            full_name="Asha Mwangi",
            phone="",
            role=UserRole.CANDIDATE,
            is_active=True,
            created_at="2027-01-01T00:00:00Z",
            password_hash="nope",
        )


async def test_geography_schemas_validate_off_mapped_instances(
    session: AsyncSession,
) -> None:
    county, constituency, ward, centre = await make_geography(session)
    station = PollingStation(ward=ward, name="Parklands Primary Stream 1", code="001A")
    session.add(station)
    await session.commit()

    assert CountyRead.model_validate(county).turnout_2022_pct is None
    assert ConstituencyRead.model_validate(constituency).county_id == county.id
    assert WardRead.model_validate(ward).constituency_id == constituency.id
    assert RegistrationCentreRead.model_validate(centre).ward_id == ward.id
    assert PollingStationRead.model_validate(station).centre_name == ""


async def test_campaign_read_includes_the_derived_grain(session: AsyncSession) -> None:
    _, _, ward, _ = await make_geography(session)
    campaign = await make_campaign(session, ward, office_level=OfficeLevel.COUNTY)
    schema = CampaignRead.model_validate(campaign)
    assert schema.operational_grain is OperationalGrain.WARD
    assert schema.office_level is OfficeLevel.COUNTY


async def test_target_read_includes_derived_progress_but_not_registered_voters(
    session: AsyncSession,
) -> None:
    """`registered_voters` reads a related row, so it stays out of the default
    read shape - see the module docstring in schemas/campaign.py."""
    _, _, ward, _ = await make_geography(session)
    campaign = await make_campaign(session, ward)
    target = Target(
        campaign=campaign,
        ward=ward,
        votes_needed=1_000,
        votes_committed=250,
        projected_turnout_pct=Decimal("65.00"),
    )
    session.add(target)
    await session.commit()

    dumped = TargetRead.model_validate(target).model_dump()
    assert dumped["votes_remaining"] == 750
    assert dumped["progress_pct"] == 25.0
    assert "registered_voters" not in dumped


async def test_mobilizer_and_event_and_supporter_schemas(session: AsyncSession) -> None:
    _, _, ward, _ = await make_geography(session)
    campaign = await make_campaign(session, ward)
    mobilizer = await make_mobilizer(session, campaign, ward)
    event = Event(
        campaign=campaign,
        ward=ward,
        mobilizer=mobilizer,
        title="Parklands rally",
        number_reached=200,
        number_attended=150,
    )
    supporter = Supporter(campaign=campaign, ward=ward, full_name="Wanjiku N.")
    session.add_all([event, supporter])
    await session.commit()

    assert MobilizerRead.model_validate(mobilizer).full_name == "Juma Otieno"

    event_schema = EventRead.model_validate(event)
    assert event_schema.turnout_pct == 75.0
    assert event_schema.status is EventStatus.PLANNED

    assert SupporterRead.model_validate(supporter).consent_given is False


def test_every_schema_declares_from_attributes() -> None:
    schemas = [
        CampaignRead,
        ConstituencyRead,
        CountyRead,
        EventRead,
        MobilizerRead,
        PollingStationRead,
        RegistrationCentreRead,
        SupporterRead,
        TargetRead,
        UserRead,
        WardRead,
    ]
    for schema in schemas:
        assert schema.model_config.get("from_attributes") is True, schema.__name__
