"""The bundled CSVs load, and the demo builds over them; both run against `backend/data`."""

from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    Campaign,
    CampaignMember,
    Constituency,
    County,
    Mobilizer,
    OfficeLevel,
    Target,
    User,
    UserRole,
    Ward,
)
from backend.security import verify_password
from backend.seed.demo import DEMO_CAMPAIGN_TITLE, seed_demo
from backend.seed.reference import (
    CAW_CSV,
    CENTRES_CSV,
    COUNTY_RESULTS_CSV,
    COUNTY_VOTERS_CSV,
    import_centres,
    import_geography,
    normalise,
    rows,
    to_int,
)
from backend.services.accounts import add_member, add_mobilizer, new_login
from tests.factories import fresh_password, members_of

# Published IEBC figures for the 2022 register.
KENYA_COUNTIES = 47
KENYA_CONSTITUENCIES = 290
KENYA_WARDS = 1450


def test_the_bundled_csvs_are_present() -> None:
    for path in (CAW_CSV, COUNTY_VOTERS_CSV, COUNTY_RESULTS_CSV):
        assert path.exists(), f"{path} is missing"


def test_headers_are_read_with_their_double_space_squeezed_out() -> None:
    first = next(rows(CAW_CSV))
    assert "Constituency Name" in first
    assert first["County Name"] == "Mombasa"


def test_a_count_reads_through_commas_and_blanks() -> None:
    assert to_int("17,817") == 17_817
    assert to_int("") == 0
    assert to_int(None) == 0


def test_names_match_regardless_of_case_and_spacing() -> None:
    assert normalise("  kahawa   west ") == normalise("Kahawa West") == "KAHAWA WEST"
    assert normalise(None) == ""


async def test_the_whole_country_loads(session: AsyncSession) -> None:
    summary = await import_geography(session)

    assert summary.counties == KENYA_COUNTIES
    assert summary.constituencies == KENYA_CONSTITUENCIES
    assert summary.wards == KENYA_WARDS
    assert await session.scalar(select(func.count()).select_from(Ward)) == KENYA_WARDS


async def test_registered_voters_match_the_published_figures(session: AsyncSession) -> None:
    await import_geography(session)
    mombasa = (await session.execute(select(County).where(County.name == "Mombasa"))).scalar_one()
    assert mombasa.registered_voters == 641_913

    port_reitz = (await session.execute(select(Ward).where(Ward.name == "Port Reitz"))).scalar_one()
    assert port_reitz.registered_voters == 17_817


async def test_turnout_is_votes_cast_over_the_register(session: AsyncSession) -> None:
    """Mombasa 2022: (277,301 valid + 3,812 rejected) / 641,913 = 43.79%."""
    await import_geography(session)
    mombasa = (await session.execute(select(County).where(County.name == "Mombasa"))).scalar_one()
    assert mombasa.turnout_2022_pct == Decimal("43.79")


async def test_every_county_gets_a_turnout(session: AsyncSession) -> None:
    summary = await import_geography(session)
    assert summary.turnout_set == KENYA_COUNTIES


async def test_turnout_needs_the_register_to_divide_by(session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="county_voters"):
        await import_geography(session, county_voters=None, county_results=COUNTY_RESULTS_CSV)


async def test_loading_twice_updates_rather_than_duplicates(session: AsyncSession) -> None:
    await import_geography(session)
    await import_geography(session)
    assert await session.scalar(select(func.count()).select_from(County)) == KENYA_COUNTIES
    assert await session.scalar(select(func.count()).select_from(Ward)) == KENYA_WARDS


async def test_centres_need_wards_first(session: AsyncSession, tmp_path) -> None:
    csv_path = tmp_path / "centres.csv"
    csv_path.write_text(
        "county_code,const_name,ward_name,centre_code,centre_name,registered_voters\n"
    )
    with pytest.raises(ValueError, match="import_geography first"):
        await import_centres(session, csv_path)


async def test_centres_attach_to_their_ward(session: AsyncSession, tmp_path) -> None:
    await import_geography(session)
    csv_path = tmp_path / "centres.csv"
    csv_path.write_text(
        "county_code,const_name,ward_name,centre_code,centre_name,registered_voters\n"
        "47,ROYSAMBU,Zimmerman,001,ZIMMERMAN PRIMARY SCHOOL,2500\n"
        "47,Roysambu,zimmerman,002,Roysambu Social Hall,1800\n"
        "99,Nowhere,Nowhere,003,Ghost Centre,100\n"
    )

    summary = await import_centres(session, csv_path)

    assert summary.centres == 2
    assert summary.unmatched == [("Nowhere", "Ghost Centre")]
    zimmerman = (
        await session.execute(
            select(Ward).where(Ward.name == "Zimmerman").options(selectinload(Ward.centres))
        )
    ).scalar_one()
    assert {c.name for c in zimmerman.centres} == {
        "ZIMMERMAN PRIMARY SCHOOL",
        "Roysambu Social Hall",
    }
    assert sum(c.registered_voters or 0 for c in zimmerman.centres) == 4_300


async def test_reloading_centres_updates_them_in_place(session: AsyncSession, tmp_path) -> None:
    await import_geography(session)
    csv_path = tmp_path / "centres.csv"
    header = "county_code,const_name,ward_name,centre_code,centre_name,registered_voters\n"
    csv_path.write_text(header + "47,Roysambu,Zimmerman,001,Zimmerman Primary,2500\n")
    await import_centres(session, csv_path)

    csv_path.write_text(header + "47,Roysambu,Zimmerman,001,Zimmerman Primary,2600\n")
    summary = await import_centres(session, csv_path)

    assert summary.centres == 1
    assert summary.wards_covered == 1


def test_the_two_sources_spell_a_ward_differently_and_still_match() -> None:
    assert normalise("Ziwa la Ng\u2019ombe") == normalise("ZIWA LA NG'OMBE")
    assert normalise("Njabini/Kiburu") == normalise("NJABINI\\KIBURU")
    assert normalise("Ziwani/Kariokor") == normalise("ZIWANI/KARIOKOR")


def test_the_bundled_centres_file_is_present() -> None:
    assert CENTRES_CSV.exists(), "data/centres.csv is missing"


async def test_every_centre_that_belongs_to_a_ward_lands(session: AsyncSession) -> None:
    await import_geography(session)

    summary = await import_centres(session, CENTRES_CSV)

    assert summary.unmatched == []
    assert summary.wards_covered == KENYA_WARDS
    assert summary.centres > 27_000


async def test_the_diaspora_and_prisons_are_left_out_rather_than_failing(
    session: AsyncSession,
) -> None:
    await import_geography(session)

    summary = await import_centres(session, CENTRES_CSV)

    assert summary.skipped_special > 100
    assert summary.unmatched == []


async def test_a_ward_name_the_pdf_cut_short_still_matches(session: AsyncSession, tmp_path) -> None:
    await import_geography(session)
    csv_path = tmp_path / "centres.csv"
    csv_path.write_text(
        "county_code,const_name,ward_name,centre_code,centre_name,registered_voters\n"
        "47,KIBRA,WOODLEY/KENYATTA GOLF COU,001,Upper Hill Sec Sch,900\n"
    )

    summary = await import_centres(session, csv_path)

    assert summary.centres == 1
    assert summary.unmatched == []
    ward = (
        await session.execute(
            select(Ward)
            .where(Ward.name == "Woodley/Kenyatta Golf Course")
            .options(selectinload(Ward.centres))
        )
    ).scalar_one()
    assert [c.name for c in ward.centres] == ["Upper Hill Sec Sch"]


async def test_a_name_too_short_to_be_sure_of_is_not_guessed_at(
    session: AsyncSession, tmp_path
) -> None:
    await import_geography(session)
    csv_path = tmp_path / "centres.csv"
    csv_path.write_text(
        "county_code,const_name,ward_name,centre_code,centre_name,registered_voters\n"
        "47,KIBRA,WOOD,001,Somewhere,900\n"
    )

    summary = await import_centres(session, csv_path)

    assert summary.centres == 0
    assert len(summary.unmatched) == 1


async def test_an_ambiguous_prefix_is_not_guessed_at(session: AsyncSession, tmp_path) -> None:
    await import_geography(session)
    constituency = (
        await session.execute(select(Constituency).where(Constituency.name == "Roysambu"))
    ).scalar_one()
    session.add_all(
        [
            Ward(constituency=constituency, name="Kahawa Sukari", registered_voters=1),
            Ward(constituency=constituency, name="Kahawa Squatters", registered_voters=1),
        ]
    )
    await session.commit()
    csv_path = tmp_path / "centres.csv"
    csv_path.write_text(
        "county_code,const_name,ward_name,centre_code,centre_name,registered_voters\n"
        "47,ROYSAMBU,KAHAWA S,001,Somewhere,900\n"
    )

    summary = await import_centres(session, csv_path)

    assert summary.centres == 0
    assert len(summary.unmatched) == 1


async def test_a_ward_s_centres_add_up_to_its_register(session: AsyncSession) -> None:
    await import_geography(session)
    await import_centres(session, CENTRES_CSV)

    ward = (
        await session.execute(
            select(Ward).where(Ward.name == "Zimmerman").options(selectinload(Ward.centres))
        )
    ).scalar_one()

    assert sum(c.registered_voters or 0 for c in ward.centres) == ward.registered_voters


async def test_a_ward_campaign_now_has_centres_to_target(session: AsyncSession) -> None:
    from backend.services.targets import generate_targets

    await import_geography(session)
    await import_centres(session, CENTRES_CSV)
    ward = (await session.execute(select(Ward).where(Ward.name == "Zimmerman"))).scalar_one()
    candidate = User(username="peter", role=UserRole.CANDIDATE)
    campaign = Campaign(title="Peter for Zimmerman", office_level=OfficeLevel.WARD, ward=ward)
    session.add_all([candidate, campaign])
    await session.flush()
    session.add(
        CampaignMember(campaign_id=campaign.id, user_id=candidate.id, role=UserRole.CANDIDATE)
    )
    await session.commit()

    summary = await generate_targets(session, campaign)

    assert summary.units == 3
    assert summary.note is None
    assert summary.total_registered == ward.registered_voters
    assert summary.win_number > 0


async def _demo(session: AsyncSession, **kwargs):
    await import_geography(session)
    return await seed_demo(session, **kwargs)


async def _user(session: AsyncSession, username: str) -> User:
    return await session.scalar(
        select(User).where(User.username == username).options(selectinload(User.memberships))
    )


async def test_the_demo_needs_the_reference_data(session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="Roysambu"):
        await seed_demo(session)


async def test_the_demo_builds_its_campaign_team_and_two_logins_on_no_campaign(
    session: AsyncSession,
) -> None:
    summary = await _demo(session)

    assert [username for username, _, _ in summary.sign_ins] == [
        "aspirant",
        "manager",
        "mobilizer",
        "newaspirant",
        "newmanager",
    ]
    printed = [password for _, password, _ in summary.sign_ins]
    assert len(set(printed)) == len(printed)
    for username, password, _ in summary.sign_ins:
        assert len(password) >= 12
        assert verify_password(password, (await _user(session, username)).password_hash)

    roysambu = await session.scalar(
        select(Constituency)
        .where(Constituency.name == "Roysambu")
        .options(selectinload(Constituency.wards))
    )
    (campaign,) = await session.scalars(select(Campaign))
    assert summary.units == len(roysambu.wards)
    assert summary.win_number > 0
    assert await members_of(session, campaign.id) == {
        "aspirant": "candidate",
        "manager": "manager",
        "mobilizer": "mobilizer",
    }
    for fresh in ("newaspirant", "newmanager"):
        assert (await _user(session, fresh)).memberships == []

    mobilizer = await session.scalar(
        select(User)
        .where(User.username == "mobilizer")
        .options(selectinload(User.mobilizer_profile))
    )
    assert mobilizer.mobilizer_profile.ward_id is not None
    targets = list(await session.scalars(select(Target)))
    staffed = {m.ward_id for m in await session.scalars(select(Mobilizer))}
    assert 0 < len(staffed) < len(targets)
    assert any(t.votes_committed >= (t.votes_needed or 0) for t in targets)
    assert any(t.votes_committed == 0 for t in targets)


@pytest.mark.parametrize(("given", "default"), [(True, False), (False, True), (True, True)])
async def test_one_password_for_every_demo_login_when_given_or_set_as_the_default(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    fresh_settings: None,
    given: bool,
    default: bool,
) -> None:
    pinned, shared = fresh_password(), fresh_password()
    if default:
        monkeypatch.setenv("DEFAULT_USER_PASSWORD", shared)

    summary = await _demo(session, password=pinned if given else None)

    expected = pinned if given else shared
    assert {password for _, password, _ in summary.sign_ins} == {expected}
    assert verify_password(expected, (await _user(session, "manager")).password_hash)


async def test_re_running_resets_passwords_and_rebuilds_the_one_demo_campaign(
    session: AsyncSession,
) -> None:
    first = await _demo(session)
    targets = await session.scalar(select(func.count()).select_from(Target))
    (campaign,) = await session.scalars(select(Campaign))
    campaign.title = "Renamed by an admin"
    await session.commit()

    second = await seed_demo(session)

    assert {p for _, p, _ in first.sign_ins}.isdisjoint({p for _, p, _ in second.sign_ins})
    for username, password, _ in second.sign_ins:
        assert verify_password(password, (await _user(session, username)).password_hash)
    assert list(await session.scalars(select(Campaign.title))) == [DEMO_CAMPAIGN_TITLE]
    assert await session.scalar(select(func.count()).select_from(Target)) == targets
    assert await session.scalar(select(func.count()).select_from(User)) == 5


async def test_re_running_puts_the_fresh_logins_back_on_no_campaign(session: AsyncSession) -> None:
    await _demo(session)
    roysambu = await session.scalar(select(Constituency).where(Constituency.name == "Roysambu"))
    theirs = Campaign(
        title="Peter for Roysambu",
        office_level=OfficeLevel.CONSTITUENCY,
        constituency_id=roysambu.id,
    )
    session.add(theirs)
    await session.flush()
    await add_member(session, theirs.id, await _user(session, "newaspirant"))
    await add_member(session, theirs.id, await _user(session, "newmanager"))
    await session.commit()

    await seed_demo(session)

    session.expire_all()
    for fresh in ("newaspirant", "newmanager"):
        assert (await _user(session, fresh)).memberships == []
    assert list(await session.scalars(select(Campaign.title))) == [DEMO_CAMPAIGN_TITLE]


async def test_re_running_leaves_every_ground_login_a_mobilizer_on_that_campaign(
    session: AsyncSession,
) -> None:
    await import_geography(session)
    roysambu = await session.scalar(
        select(Constituency)
        .where(Constituency.name == "Roysambu")
        .options(selectinload(Constituency.wards))
    )
    ward = sorted(roysambu.wards, key=lambda w: w.name)[0]
    elsewhere = Campaign(
        title="Peter for Roysambu",
        office_level=OfficeLevel.CONSTITUENCY,
        constituency_id=roysambu.id,
    )
    session.add(elsewhere)
    await session.flush()
    elsewhere_id = elsewhere.id
    squatter, _ = await new_login(session, username="newmanager", role=UserRole.MOBILIZER)
    await add_mobilizer(session, elsewhere, ward.id, squatter)
    await session.commit()
    await seed_demo(session)
    demo = await session.scalar(select(Campaign).where(Campaign.title == DEMO_CAMPAIGN_TITLE))
    kip, _ = await new_login(session, username="kip", role=UserRole.MOBILIZER)
    await add_mobilizer(session, demo, ward.id, kip)
    await session.commit()

    await seed_demo(session)

    assert await session.scalar(select(User.id).where(User.username == "kip")) is None
    assert await session.scalar(select(User.role).where(User.username == "newmanager")) is (
        UserRole.MANAGER
    )
    unlinked = select(func.count()).select_from(Mobilizer)
    unlinked = unlinked.where(Mobilizer.campaign_id == elsewhere_id, Mobilizer.user_id.is_(None))
    assert await session.scalar(unlinked) == 1
    grounded = await session.execute(
        select(Mobilizer.campaign_id, User.role, CampaignMember.campaign_id)
        .join(User, User.id == Mobilizer.user_id)
        .outerjoin(CampaignMember, CampaignMember.user_id == User.id)
    )
    for ground_campaign, role, member_campaign in grounded:
        assert (role, member_campaign) == (UserRole.MOBILIZER, ground_campaign)


async def test_the_demo_will_not_replace_a_superuser_with_a_demo_username(
    session: AsyncSession,
) -> None:
    await _demo(session)
    await session.execute(
        User.__table__.update().where(User.username == "manager").values(is_superuser=True)
    )
    await session.commit()

    with pytest.raises(ValueError, match="manager is a superuser"):
        await seed_demo(session)

    await session.rollback()
    assert await session.scalar(select(User.is_superuser).where(User.username == "manager"))
    assert list(await session.scalars(select(Campaign.title))) == [DEMO_CAMPAIGN_TITLE]


async def test_a_demo_that_fails_part_way_keeps_the_old_demo(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.seed import demo

    await _demo(session)
    before = set(await session.scalars(select(User.id)))

    async def _broken(*_):
        raise RuntimeError("the ground game failed")

    monkeypatch.setattr(demo, "_seed_ground_game", _broken)
    with pytest.raises(RuntimeError):
        await seed_demo(session)

    await session.rollback()
    assert set(await session.scalars(select(User.id))) == before
    assert await session.scalar(select(func.count()).select_from(Target)) > 0
    assert await session.scalar(select(func.count()).select_from(Mobilizer)) > 0
