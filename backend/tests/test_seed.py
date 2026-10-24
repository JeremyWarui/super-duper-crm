"""The bundled CSVs load, and the demo builds over them; both run against `backend/data`."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    Campaign,
    Constituency,
    Mobilizer,
    Target,
    User,
    Ward,
)
from backend.security import verify_password
from backend.seed.demo import DEMO_USERNAMES, seed_demo
from backend.seed.reference import (
    CENTRES_CSV,
    import_centres,
    import_geography,
)
from tests.factories import members_of

# Published IEBC figures for the 2022 register.
KENYA_COUNTIES = 47
KENYA_CONSTITUENCIES = 290
KENYA_WARDS = 1450


async def test_the_whole_country_loads(session: AsyncSession) -> None:
    summary = await import_geography(session)

    assert summary.counties == KENYA_COUNTIES
    assert summary.constituencies == KENYA_CONSTITUENCIES
    assert summary.wards == KENYA_WARDS
    assert await session.scalar(select(func.count()).select_from(Ward)) == KENYA_WARDS


async def test_every_centre_that_belongs_to_a_ward_lands(session: AsyncSession) -> None:
    await import_geography(session)

    summary = await import_centres(session, CENTRES_CSV)

    assert summary.unmatched == []
    assert summary.wards_covered == KENYA_WARDS
    assert summary.centres > 27_000


async def _demo(session: AsyncSession, **kwargs):
    await import_geography(session)
    return await seed_demo(session, **kwargs)


async def _user(session: AsyncSession, username: str) -> User:
    return await session.scalar(
        select(User).where(User.username == username).options(selectinload(User.memberships))
    )


async def test_the_demo_builds_its_campaign_and_team(
    session: AsyncSession,
) -> None:
    summary = await _demo(session)

    assert [username for username, _, _ in summary.sign_ins] == [
        "aspirant",
        "manager",
        "mobilizer",
    ]
    # The demo clears only its own logins; a real login with another name is never touched.
    assert DEMO_USERNAMES == ("aspirant", "manager", "mobilizer")
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
