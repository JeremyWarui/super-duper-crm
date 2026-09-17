"""The demo: one campaign with a sign-in per role, and two logins on no campaign."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    Campaign,
    CampaignMember,
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
from backend.security import hash_password, new_password
from backend.services.accounts import add_member
from backend.services.admin import remove_campaign
from backend.services.targets import generate_targets

DEMO_USERNAMES = ("aspirant", "manager", "mobilizer", "newaspirant", "newmanager")

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
    """username, password, what that role sees."""


def demo_passwords(password: str | None = None) -> dict[str, str]:
    """A password per demo account: the one given, else DEFAULT_USER_PASSWORD, else generated."""
    return {username: password or new_password() for username in DEMO_USERNAMES}


def _user(
    session: AsyncSession,
    username: str,
    role: UserRole,
    first_name: str,
    last_name: str,
    passwords: dict[str, str],
    phone: str = "",
) -> User:
    """A new demo login with this run's password."""
    user = User(
        username=username,
        role=role,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        password_hash=hash_password(passwords[username]),
    )
    session.add(user)
    return user


async def _clear(session: AsyncSession) -> None:
    """Delete the demo logins, the campaigns they are candidates on, and every login on those."""
    logins = select(User.id).where(User.username.in_(DEMO_USERNAMES))
    standing = await session.scalars(
        select(CampaignMember.campaign_id).where(
            CampaignMember.user_id.in_(logins), CampaignMember.role == UserRole.CANDIDATE
        )
    )
    for campaign_id in list(standing):
        await remove_campaign(session, campaign_id)
    await session.execute(delete(User).where(User.username.in_(DEMO_USERNAMES)))


async def seed_demo(session: AsyncSession, *, password: str | None = None) -> DemoSummary:
    """Build the demo over loaded geography; re-running deletes the old demo and builds it again."""
    passwords = demo_passwords(password)
    constituency = await session.scalar(
        select(Constituency)
        .join(County)
        .where(County.name == DEMO_COUNTY, Constituency.name == DEMO_CONSTITUENCY)
        .options(selectinload(Constituency.wards))
    )
    if constituency is None:
        raise ValueError(
            f"{DEMO_CONSTITUENCY} is not loaded - run the reference seed before the demo."
        )
    if not constituency.wards:
        raise ValueError(f"{DEMO_CONSTITUENCY} has no wards loaded.")
    admins = await session.scalars(
        select(User.username).where(User.username.in_(DEMO_USERNAMES), User.is_superuser)
    )
    if taken := list(admins):
        raise ValueError(f"{', '.join(taken)} is a superuser, and the demo replaces that login.")
    await _clear(session)

    aspirant = _user(
        session, "aspirant", UserRole.CANDIDATE, "Jane", "Wanjiru", passwords, "+254700000001"
    )
    manager = _user(
        session, "manager", UserRole.MANAGER, "Amina", "Kariuki", passwords, "+254700000002"
    )
    mobilizer_user = _user(
        session, "mobilizer", UserRole.MOBILIZER, "Juma", "Otieno", passwords, "+254700000003"
    )
    _user(session, "newaspirant", UserRole.CANDIDATE, "Peter", "Kimani", passwords, "+254700000004")
    _user(session, "newmanager", UserRole.MANAGER, "Grace", "Otieno", passwords, "+254700000005")
    campaign = Campaign(
        title=DEMO_CAMPAIGN_TITLE,
        office_level=OfficeLevel.CONSTITUENCY,
        constituency_id=constituency.id,
        election_date=datetime(2027, 8, 10, tzinfo=UTC).date(),
    )
    session.add(campaign)
    await session.flush()
    for member in (aspirant, manager, mobilizer_user):
        await add_member(session, campaign.id, member)

    summary = await generate_targets(session, campaign)

    wards = sorted(constituency.wards, key=lambda w: w.name)

    await _seed_ground_game(session, campaign, wards, mobilizer_user)
    await session.commit()

    return DemoSummary(
        campaign_title=campaign.title,
        office=f"{OfficeLevel.CONSTITUENCY.label} - {constituency.name}",
        units=summary.units,
        win_number=summary.win_number,
        sign_ins=[
            ("aspirant", passwords["aspirant"], "Candidate: the cockpit, adds mobilizers"),
            ("manager", passwords["manager"], "Campaign manager: the full war room"),
            ("mobilizer", passwords["mobilizer"], f"Mobilizer: {wards[0].name} only"),
            (
                "newaspirant",
                passwords["newaspirant"],
                "Candidate with no campaign: starts at setup",
            ),
            (
                "newmanager",
                passwords["newmanager"],
                "Manager with no campaign: starts at setup, and is asked for the aspirant",
            ),
        ],
    )


async def _seed_ground_game(
    session: AsyncSession,
    campaign: Campaign,
    wards: list[Ward],
    mobilizer_user: User,
) -> None:
    """Mobilizers, events and supporters, spread unevenly across the wards."""
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
    """Spread progress across the staffed wards, from met to barely started."""
    shares = [1.05, 0.8, 0.55, 0.3]
    targets = await session.scalars(select(Target).where(Target.campaign_id == campaign.id))
    by_ward = {target.ward_id: target for target in targets}
    for index, ward in enumerate(staffed):
        target = by_ward.get(ward.id)
        if target is None or not target.votes_needed:
            continue
        target.votes_committed = int(target.votes_needed * shares[index % len(shares)])
