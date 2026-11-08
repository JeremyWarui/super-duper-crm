"""The party demo: a set-up party installation with its website, offices and one campaign."""

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Aspirant,
    AspirantStatus,
    Campaign,
    CandidateProfile,
    Constituency,
    County,
    OrganisationType,
    PartyConsentChannel,
    PartyMember,
    PartyMemberStatus,
    PartyRoleName,
    Seat,
    User,
    Ward,
)
from backend.schemas.setup import SetupRequest, SetupSite, SetupSuperuser
from backend.seed.demo import DEMO_CAMPAIGN_TITLE, demo_email, seed_demo
from backend.seed.sign_ins import SignIn
from backend.seed.site import (
    SETTINGS,
    portrait,
    seed_branches,
    seed_home,
    seed_news,
    seed_site,
)
from backend.services import admin, setup
from backend.services.accounts import new_login
from backend.services.consent import PARTY_WORDING
from backend.services.errors import Refused
from backend.services.rich_text import from_plain

# username, office, first name, last name, phone
OFFICERS = [
    ("membership", PartyRoleName.MEMBERSHIP_OFFICER, "Peter", "Kamau", "+254711000001"),
    ("nominations", PartyRoleName.NOMINATIONS_OFFICER, "Faith", "Achieng", "+254711000002"),
    ("comms", PartyRoleName.COMMS_OFFICER, "Brian", "Mutua", "+254711000003"),
]
OFFICE_SEES = {
    PartyRoleName.MEMBERSHIP_OFFICER: "Members, Volunteers, Branches, Data requests",
    PartyRoleName.NOMINATIONS_OFFICER: "Aspirants and nomination fees (Payments in)",
    PartyRoleName.COMMS_OFFICER: "Messages to members",
}
PENDING_MEMBERS = [("Mercy Chebet", "+254711000011"), ("Daniel Omondi", "+254711000012")]
SUBMITTED_ASPIRANT = ("Samuel Kiprono", "+254711000021")
JANE_PHONE = "+254700000001"


def _member(name: str, phone: str, ward: Ward, status: PartyMemberStatus) -> PartyMember:
    return PartyMember(
        full_name=name,
        first_name=name.split()[0],
        phone=phone,
        ward_id=ward.id,
        status=status,
        consent_wording=PARTY_WORDING[PartyConsentChannel.WEB_FORM],
        consent_channel=PartyConsentChannel.WEB_FORM,
        consent_at=datetime.now(UTC),
    )


async def _roysambu_wards(session: AsyncSession) -> list[Ward]:
    wards = await session.scalars(
        select(Ward)
        .join(Constituency)
        .join(County)
        .where(County.name == "Nairobi City", Constituency.name == "Roysambu")
        .order_by(Ward.name)
    )
    return list(wards)


async def _set_up(session: AsyncSession, password: str) -> User:
    """The first-run setup as /setup runs it: a party with its superuser."""
    token = await setup.new_token(session)
    await setup.run(
        session,
        SetupRequest(
            token=token,
            organisation_type=OrganisationType.PARTY,
            site=SetupSite(
                name=SETTINGS["name"],
                primary_colour=SETTINGS["primary_colour"],
                secondary_colour=SETTINGS["secondary_colour"],
            ),
            superuser=SetupSuperuser(
                username="admin",
                email=demo_email("admin"),
                password=password,
                first_name="Grace",
                last_name="Njeri",
            ),
        ),
    )
    return await session.scalar(select(User).where(User.username == "admin"))


async def _officers(
    session: AsyncSession, admin_user: User, ward: Ward, password: str
) -> list[SignIn]:
    """A staff login for each party office, linked to its approved member."""
    sign_ins = []
    for username, office, first, last, phone in OFFICERS:
        member = _member(f"{first} {last}", phone, ward, PartyMemberStatus.APPROVED)
        session.add(member)
        await session.flush()
        login, _ = await new_login(
            session,
            username=username,
            role=None,
            password=password,
            email=demo_email(username),
            first_name=first,
            last_name=last,
            phone=phone,
        )
        login.party_member_id = member.id
        await session.flush()
        await admin.grant_party_role(session, login.id, office, actor=admin_user)
        sign_ins.append(SignIn(demo_email(username), office.label, OFFICE_SEES[office]))
    return sign_ins


async def _jane_is_an_aspirant(session: AsyncSession, ward: Ward) -> None:
    """Make the demo campaign an approved aspirant's hosted workspace with a public profile."""
    campaign = await session.scalar(select(Campaign).where(Campaign.title == DEMO_CAMPAIGN_TITLE))
    member = _member("Jane Wanjiru", JANE_PHONE, ward, PartyMemberStatus.APPROVED)
    session.add(member)
    await session.flush()
    aspirant = Aspirant(
        member_id=member.id,
        seat=Seat.MP,
        constituency_id=campaign.constituency_id,
        status=AspirantStatus.APPROVED,
        campaign_id=campaign.id,
    )
    session.add(aspirant)
    await session.flush()
    login = await session.scalar(select(User).where(User.username == "aspirant"))
    login.party_member_id = member.id
    session.add(
        CandidateProfile(
            campaign_id=campaign.id,
            aspirant_id=aspirant.id,
            photo_url=portrait("akinyi"),
            slogan="Roysambu works when we work together",
            bio=from_plain("Jane Wanjiru is a teacher and a Pamoja Party member from Roysambu."),
            priorities=[
                {"title": "Youth jobs", "text": "An apprenticeship desk in every ward."},
                {"title": "Clean water", "text": "Repair the Githurai and Zimmerman lines."},
            ],
            office_address="Campaign office, Roysambu",
            office_phone=SETTINGS["contact_phone"],
            published=True,
        )
    )


async def _waiting_work(session: AsyncSession, ward: Ward) -> None:
    """Join requests and a nomination waiting for the officers."""
    for name, phone in PENDING_MEMBERS:
        session.add(_member(name, phone, ward, PartyMemberStatus.PENDING))
    name, phone = SUBMITTED_ASPIRANT
    member = _member(name, phone, ward, PartyMemberStatus.APPROVED)
    session.add(member)
    await session.flush()
    session.add(
        Aspirant(
            member_id=member.id,
            seat=Seat.MCA,
            ward_id=ward.id,
            status=AspirantStatus.SUBMITTED,
        )
    )


async def build_party(session: AsyncSession, *, password: str, today: date) -> list[SignIn]:
    """Set up an empty database as the party demo and return its sign-ins."""
    if await setup.is_set_up(session):
        raise Refused("This database is already set up; the party demo needs an empty one.")
    wards = await _roysambu_wards(session)
    if not wards:
        raise Refused("Load the reference data first: campaign-crm seed.")

    admin_user = await _set_up(session, password)
    await seed_branches(session, today)
    await seed_home(session)
    await seed_site(session, today)
    await seed_news(session, today)

    sign_ins = [
        SignIn(demo_email("admin"), "Party super admin", "Dashboard, every party page, Console")
    ]
    sign_ins += await _officers(session, admin_user, wards[0], password)

    demo = await seed_demo(session, password=password)
    await _jane_is_an_aspirant(session, wards[0])
    await _waiting_work(session, wards[-1])
    await session.commit()

    sign_ins += [SignIn(email, *sees.split(": ", 1)) for email, _, sees in demo.sign_ins]
    return sign_ins
