"""The demo: one campaign with a sign-in per role."""

import secrets
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    Campaign,
    CampaignMember,
    Constituency,
    ContactMethod,
    County,
    CrmPlan,
    EntryKind,
    Event,
    EventStatus,
    OfficeLevel,
    PartyConsentChannel,
    PartyMember,
    PartyMemberStatus,
    Profession,
    ReceiptMethod,
    RegistrationCentre,
    Seat,
    SubscriptionEntry,
    Supporter,
    SupportLevel,
    Target,
    User,
    UserKind,
    UserRole,
    VolunteerProfile,
    Ward,
)
from backend.security import hash_password, new_password
from backend.services.accounts import add_member, add_mobilizer
from backend.services.admin import remove_campaign
from backend.services.billing import extended, today
from backend.services.consent import PARTY_WORDING, VOLUNTEER_WORDING
from backend.services.targets import generate_targets

DEMO_USERNAMES = ("aspirant", "manager", "mobilizer", "volunteer")
DEMO_EMAIL_DOMAIN = "demo.pamoja.test"
DEMO_MEMBER_PHONE = "+254700000009"

DEMO_COUNTY = "Nairobi City"
DEMO_CONSTITUENCY = "Roysambu"
DEMO_CAMPAIGN_TITLE = "Jane for Roysambu"
DEMO_PLAN = "Demo yearly"


@dataclass
class DemoSummary:
    campaign_title: str
    office: str
    units: int
    win_number: int
    paid_until: date
    sign_ins: list[tuple[str, str, str]]
    """email, password, what that login sees."""


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
        email=demo_email(username),
        phone=phone,
        password_hash=hash_password(passwords[username]),
    )
    session.add(user)
    return user


def demo_email(username: str) -> str:
    return f"{username}@{DEMO_EMAIL_DOMAIN}"


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
    await session.execute(delete(PartyMember).where(PartyMember.phone == DEMO_MEMBER_PHONE))


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
    campaign = Campaign(
        title=DEMO_CAMPAIGN_TITLE,
        office_level=OfficeLevel.CONSTITUENCY,
        seat=Seat.MP,
        constituency_id=constituency.id,
        election_date=datetime(2027, 8, 10, tzinfo=UTC).date(),
    )
    session.add(campaign)
    await session.flush()
    for member in (aspirant, manager):
        await add_member(session, campaign.id, member)

    summary = await generate_targets(session, campaign)

    wards = sorted(constituency.wards, key=lambda w: w.name)

    await _seed_ground_game(session, campaign, wards, mobilizer_user)
    await _volunteer(session, wards[0], passwords)
    paid_until = await _pay(session, campaign)
    await session.commit()

    return DemoSummary(
        campaign_title=campaign.title,
        office=f"{Seat.MP.label} seat - {constituency.name}",
        units=summary.units,
        win_number=summary.win_number,
        paid_until=paid_until,
        sign_ins=[
            (demo_email(name), passwords[name], sees)
            for name, sees in (
                ("aspirant", "Candidate: the cockpit, adds mobilizers"),
                ("manager", "Campaign manager: the full war room"),
                ("mobilizer", f"Mobilizer: {wards[0].name} only"),
                ("volunteer", "Party member who volunteers: their member account"),
            )
        ],
    )


async def _volunteer(session: AsyncSession, ward: Ward, passwords: dict[str, str]) -> None:
    """An approved party member who volunteers, with their own member login."""
    centre = await session.scalar(
        select(RegistrationCentre)
        .where(RegistrationCentre.ward_id == ward.id)
        .order_by(RegistrationCentre.name)
    )
    now = datetime.now(UTC)
    member = PartyMember(
        full_name="Wanjiku Muthoni",
        first_name="Wanjiku",
        phone=DEMO_MEMBER_PHONE,
        email=demo_email("volunteer"),
        ward_id=ward.id,
        registration_centre_id=centre.id if centre else None,
        status=PartyMemberStatus.APPROVED,
        consent_wording=PARTY_WORDING[PartyConsentChannel.WEB_FORM],
        consent_channel=PartyConsentChannel.WEB_FORM,
        consent_at=now,
    )
    session.add(member)
    await session.flush()
    session.add_all(
        [
            VolunteerProfile(
                member_id=member.id,
                first_name="Wanjiku",
                last_name="Muthoni",
                phone=member.phone,
                email=member.email,
                ward_id=ward.id,
                registration_centre_id=member.registration_centre_id,
                profession=Profession.TEACHER,
                interests=["door_to_door", "barazas"],
                preferred_contact=ContactMethod.SMS,
                consent_wording=VOLUNTEER_WORDING,
                consent_at=now,
            ),
            User(
                username="volunteer",
                kind=UserKind.MEMBER,
                party_member_id=member.id,
                first_name="Wanjiku",
                last_name="Muthoni",
                email=member.email,
                phone=member.phone,
                password_hash=hash_password(passwords["volunteer"]),
            ),
        ]
    )
    await session.flush()


async def _pay(session: AsyncSession, campaign: Campaign) -> date:
    """Put the campaign on the demo plan and record one payment received today."""
    plan = await session.scalar(select(CrmPlan).where(CrmPlan.name == DEMO_PLAN))
    if plan is None:
        plan = CrmPlan(name=DEMO_PLAN, price_kes=120_000, duration_days=365)
        session.add(plan)
        await session.flush()
    sub = campaign.subscription
    sub.plan_id = plan.id
    sub.paid_until = extended(None, today(), plan.duration_days)
    session.add(
        SubscriptionEntry(
            subscription_id=sub.id,
            kind=EntryKind.PAYMENT,
            plan_id=plan.id,
            amount_kes=plan.price_kes,
            method=ReceiptMethod.MPESA,
            # A new reference each run: a re-run keeps the old demo's ledger.
            reference=f"DEMO-{secrets.token_hex(4).upper()}",
            received_on=today(),
            days=plan.duration_days,
            paid_until_after=sub.paid_until,
            note="Demo payment from the seed.",
        )
    )
    await session.flush()
    return sub.paid_until


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
        mobilizer = await add_mobilizer(
            session,
            campaign,
            ward.id,
            mobilizer_user if index == 0 else None,
            full_name=f"Organiser - {ward.name}",
            phone=f"+2547{index:08d}",
        )
        mobilizers.append(mobilizer)

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
