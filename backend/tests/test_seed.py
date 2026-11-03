"""The bundled CSVs load, and the demo builds over them; both run against `backend/data`."""

from datetime import date

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    AccessState,
    Campaign,
    CampaignSubscription,
    Constituency,
    Mobilizer,
    Target,
    User,
    UserKind,
    Ward,
)
from backend.security import verify_password
from backend.seed.demo import DEMO_USERNAMES, seed_demo
from backend.seed.reference import (
    CENTRES_CSV,
    import_centres,
    import_geography,
)
from backend.seed.site import seed_site
from backend.services.billing import access, today
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

    assert [email for email, _, _ in summary.sign_ins] == [
        "aspirant@demo.mzigo.test",
        "manager@demo.mzigo.test",
        "mobilizer@demo.mzigo.test",
        "volunteer@demo.mzigo.test",
    ]
    # The demo clears only its own logins; a real login with another name is never touched.
    assert DEMO_USERNAMES == ("aspirant", "manager", "mobilizer", "volunteer")
    printed = [password for _, password, _ in summary.sign_ins]
    assert len(set(printed)) == len(printed)
    for email, password, _ in summary.sign_ins:
        assert len(password) >= 12
        user = await _user(session, email.split("@")[0])
        assert (user.email, verify_password(password, user.password_hash)) == (email, True)
    volunteer = await _user(session, "volunteer")
    assert (volunteer.kind, volunteer.party_member_id is not None) == (UserKind.MEMBER, True)

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


async def test_the_demo_campaign_is_paid_and_builds_again_on_a_rerun(
    session: AsyncSession,
) -> None:
    await _demo(session)
    summary = await seed_demo(session)

    campaign = await session.scalar(
        select(Campaign)
        .where(Campaign.title == summary.campaign_title)
        .options(selectinload(Campaign.subscription).selectinload(CampaignSubscription.entries))
    )
    sub = campaign.subscription
    (payment,) = sub.entries
    assert access(sub.paid_until, sub.hold, today()).state is AccessState.ACTIVE
    assert (payment.received_on, payment.paid_until_after) == (today(), summary.paid_until)


async def test_the_demo_site_publishes_once(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    first = await seed_site(session, date(2026, 11, 1))
    again = await seed_site(session, date(2026, 11, 1))

    leaders = (await client.get("/api/party/leaders/")).json()
    events = (await client.get("/api/party/posts/", params={"kind": "event"})).json()
    assert (first, again) == (True, False)
    assert (len(leaders), len(events)) == (6, 3)
    assert (await client.get("/api/party/")).json()["name"] == "Mzigo Demo Party"
