"""A worked example: one campaign, and one sign-in per role.

Each role sees a different app, so showing the three of them means signing in as
each in turn. The passwords here are fixed and public; they belong in a local
database and nowhere else.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    Campaign,
    Constituency,
    County,
    Event,
    EventStatus,
    Mobilizer,
    OfficeLevel,
    Supporter,
    SupportLevel,
    Target,
    User,
    UserRole,
    Ward,
)
from backend.security import hash_password
from backend.services.targets import generate_targets

DEMO_PASSWORDS = {
    "manager": "demo-manager-2027",
    "aspirant": "demo-aspirant-2027",
    "mobilizer": "demo-mobilizer-2027",
}

# Roysambu MP: the seat the prototype was checked against.
DEMO_COUNTY = "Nairobi City"
DEMO_CONSTITUENCY = "Roysambu"
DEMO_CAMPAIGN_TITLE = "Jane for Roysambu"


@dataclass
class DemoSummary:
    campaign_title: str
    office: str
    units: int
    win_number: int
    sign_ins: list[tuple[str, str, str]]


async def _user(
    session: AsyncSession,
    username: str,
    role: UserRole,
    first_name: str,
    last_name: str,
    phone: str = "",
) -> User:
    """The demo user, created if missing and reset to a known password if not."""
    user = (
        await session.execute(select(User).where(User.username == username))
    ).scalar_one_or_none()
    if user is None:
        user = User(username=username)
        session.add(user)
    user.role = role
    user.first_name = first_name
    user.last_name = last_name
    user.phone = phone
    user.is_active = True
    user.password_hash = hash_password(DEMO_PASSWORDS[username])
    return user


async def seed_demo(session: AsyncSession) -> DemoSummary:
    """Build the demo campaign over already-loaded geography.

    Re-running rebuilds it in place rather than making a second campaign.
    """
    constituency = (
        await session.execute(
            select(Constituency)
            .join(County)
            .where(County.name == DEMO_COUNTY, Constituency.name == DEMO_CONSTITUENCY)
            .options(selectinload(Constituency.wards))
        )
    ).scalar_one_or_none()
    if constituency is None:
        raise ValueError(
            f"{DEMO_CONSTITUENCY} is not loaded - run the reference seed before the demo."
        )

    aspirant = await _user(
        session, "aspirant", UserRole.CANDIDATE, "Jane", "Wanjiru", "+254700000001"
    )
    await _user(session, "manager", UserRole.MANAGER, "Amina", "Kariuki", "+254700000002")
    mobilizer_user = await _user(
        session, "mobilizer", UserRole.MOBILIZER, "Juma", "Otieno", "+254700000003"
    )
    await session.flush()

    campaign = (
        await session.execute(
            select(Campaign).where(
                Campaign.candidate_id == aspirant.id, Campaign.title == DEMO_CAMPAIGN_TITLE
            )
        )
    ).scalar_one_or_none()
    if campaign is None:
        campaign = Campaign(candidate=aspirant, title=DEMO_CAMPAIGN_TITLE)
        session.add(campaign)
    campaign.office_level = OfficeLevel.CONSTITUENCY
    campaign.constituency_id = constituency.id
    campaign.county_id = None
    campaign.ward_id = None
    campaign.election_date = datetime(2027, 8, 10, tzinfo=UTC).date()
    await session.flush()

    summary = await generate_targets(session, campaign)

    wards = sorted(constituency.wards, key=lambda w: w.name)
    if not wards:
        raise ValueError(f"{DEMO_CONSTITUENCY} has no wards loaded.")

    await _seed_ground_game(session, campaign, wards, mobilizer_user)
    await session.commit()

    return DemoSummary(
        campaign_title=campaign.title,
        office=f"{OfficeLevel.CONSTITUENCY.label} - {constituency.name}",
        units=summary.units,
        win_number=summary.win_number,
        sign_ins=[
            ("aspirant", DEMO_PASSWORDS["aspirant"], "Candidate: read-only cockpit"),
            ("manager", DEMO_PASSWORDS["manager"], "Campaign manager: the full war room"),
            ("mobilizer", DEMO_PASSWORDS["mobilizer"], f"Mobilizer: {wards[0].name} only"),
        ],
    )


async def _seed_ground_game(
    session: AsyncSession,
    campaign: Campaign,
    wards: list[Ward],
    mobilizer_user: User,
) -> None:
    """Enough mobilizers, events and supporters that the strategy read has something to say.

    Deliberately uneven: the first wards are staffed and worked, the rest are
    not, so the "go next" and "unstaffed" notes have real gaps to point at.
    """
    already = (
        await session.execute(
            select(func.count()).select_from(Mobilizer).where(Mobilizer.campaign_id == campaign.id)
        )
    ).scalar_one()
    if already:
        return

    staffed = wards[: max(len(wards) // 2, 1)]
    mobilizers = []
    for index, ward in enumerate(staffed):
        mobilizer = Mobilizer(
            campaign=campaign,
            ward=ward,
            full_name=f"Organiser - {ward.name}",
            phone=f"+2547{index:08d}",
            user=mobilizer_user if index == 0 else None,
        )
        mobilizers.append(mobilizer)
        session.add(mobilizer)

    start = datetime.now(UTC) - timedelta(days=30)
    for index, (ward, mobilizer) in enumerate(zip(staffed, mobilizers, strict=True)):
        held = 2 if index == 0 else 1
        for n in range(held):
            reached = 400 + 50 * index
            session.add(
                Event(
                    campaign=campaign,
                    ward=ward,
                    mobilizer=mobilizer,
                    title=f"{ward.name} town hall {n + 1}",
                    venue=f"{ward.name} social hall",
                    scheduled_date=start + timedelta(days=7 * index + n),
                    status=EventStatus.DONE,
                    number_reached=reached,
                    number_attended=int(reached * 0.7),
                )
            )
        session.add(
            Event(
                campaign=campaign,
                ward=ward,
                mobilizer=mobilizer,
                title=f"{ward.name} rally",
                venue=f"{ward.name} grounds",
                scheduled_date=datetime.now(UTC) + timedelta(days=7 + index),
                status=EventStatus.PLANNED,
            )
        )

    levels = [
        SupportLevel.SUPPORTER,
        SupportLevel.SUPPORTER,
        SupportLevel.UNDECIDED,
        SupportLevel.OPPOSED,
    ]
    for index, (ward, mobilizer) in enumerate(zip(staffed, mobilizers, strict=True)):
        for n in range(4):
            session.add(
                Supporter(
                    campaign=campaign,
                    ward=ward,
                    mobilizer=mobilizer,
                    full_name=f"{ward.name} supporter {n + 1}",
                    phone=f"+2547{index:04d}{n:04d}",
                    support_level=levels[n],
                    consent_given=True,
                )
            )

    await _commit_some_votes(session, campaign, staffed)


async def _commit_some_votes(
    session: AsyncSession, campaign: Campaign, staffed: list[Ward]
) -> None:
    """Spread progress across the staffed wards, from met to barely started.

    The dashboard colours a unit by progress, so a demo where everything sits at
    zero shows only one of the three states.
    """
    shares = [1.05, 0.8, 0.55, 0.3]
    targets = (
        await session.execute(select(Target).where(Target.campaign_id == campaign.id))
    ).scalars()
    by_ward = {str(target.ward_id): target for target in targets}
    for index, ward in enumerate(staffed):
        target = by_ward.get(str(ward.id))
        if target is None or not target.votes_needed:
            continue
        target.votes_committed = int(target.votes_needed * shares[index % len(shares)])
