"""The aspirant demo: a set-up aspirant installation with its candidate page, team and work."""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Campaign,
    CandidateProfile,
    Constituency,
    County,
    OrganisationType,
    PartyPost,
    PostKind,
    Seat,
    User,
    UserRole,
    Ward,
)
from backend.schemas.setup import InvitedLogin, SetupRequest, SetupSeat, SetupSite, SetupSuperuser
from backend.security import hash_password
from backend.seed.demo import demo_email, seed_ground_game
from backend.seed.sign_ins import SignIn
from backend.seed.site import BODY, PICTURE, portrait
from backend.services import setup
from backend.services.accounts import add_member, new_login
from backend.services.errors import Refused
from backend.services.rich_text import from_plain

COUNTY = "Nairobi City"
CONSTITUENCY = "Kasarani"
TITLE = "David Otieno for Kasarani"
NEWS = [
    ("David Otieno opens his Kasarani campaign office", 12, "GZLDAMHFU4"),
    ("Clean water plan for Njiru and Ruai", 5, "6B6QMRB4XI"),
]
EVENT = ("Town hall at Mwiki grounds", 9, "Mwiki grounds", "6KRBT8MYES")


async def _kasarani(session: AsyncSession) -> Constituency | None:
    return await session.scalar(
        select(Constituency)
        .join(County)
        .where(County.name == COUNTY, Constituency.name == CONSTITUENCY)
    )


async def _set_up(session: AsyncSession, kasarani: Constituency, password: str) -> Campaign:
    """The first-run setup as /setup runs it: an aspirant with their seat and candidate login."""
    token = await setup.new_token(session)
    result = await setup.run(
        session,
        SetupRequest(
            token=token,
            organisation_type=OrganisationType.ASPIRANT,
            site=SetupSite(
                name=TITLE,
                short_name="Otieno",
                primary_colour="#1d3f8f",
                secondary_colour="#f2b705",
                contact_email="office@example.com",
                contact_phone="0700 111222",
                address="Campaign office, Mwiki Road, Kasarani",
            ),
            superuser=SetupSuperuser(
                username="admin",
                email=demo_email("admin"),
                password=password,
                first_name="Kevin",
                last_name="Mwangi",
            ),
            aspirant=SetupSeat(
                title=TITLE,
                seat=Seat.MP,
                election_date=date(2027, 8, 10),
                constituency=kasarani.id,
                candidate=InvitedLogin(
                    username="candidate",
                    email=demo_email("candidate"),
                    first_name="David",
                    last_name="Otieno",
                    phone="+254722000001",
                ),
            ),
        ),
    )
    campaign = await session.get(Campaign, result.workspace)
    candidate = await session.scalar(select(User).where(User.username == "candidate"))
    candidate.password_hash = hash_password(password)
    return campaign


async def _team(session: AsyncSession, campaign: Campaign, password: str) -> User:
    """A manager on the campaign; returns the mobilizer login the ground game places."""
    manager, _ = await new_login(
        session,
        username="manager",
        role=UserRole.MANAGER,
        password=password,
        email=demo_email("manager"),
        first_name="Lucy",
        last_name="Wambui",
        phone="+254722000002",
    )
    await add_member(session, campaign.id, manager)
    mobilizer, _ = await new_login(
        session,
        username="mobilizer",
        role=UserRole.MOBILIZER,
        password=password,
        email=demo_email("mobilizer"),
        first_name="Kevin",
        last_name="Ochieng",
        phone="+254722000003",
    )
    return mobilizer


async def _site(session: AsyncSession, campaign: Campaign, today: date) -> None:
    """Publish the candidate page, two news posts and an event."""
    profile = await session.scalar(
        select(CandidateProfile).where(CandidateProfile.campaign_id == campaign.id)
    )
    profile.photo_url = portrait("david")
    profile.slogan = "Kasarani deserves better, and we will build it together"
    profile.bio = from_plain(
        "David Otieno grew up in Mwiki, trained as a civil engineer and has spent ten years "
        "building roads and water lines across Nairobi."
    )
    profile.priorities = [
        {"title": "Water", "text": "Piped water to every estate in Njiru and Ruai."},
        {"title": "Jobs", "text": "A youth skills centre in each of the five wards."},
        {"title": "Roads", "text": "Tarmac the feeder roads that flood every rainy season."},
    ]
    profile.office_address = "Campaign office, Mwiki Road, Kasarani"
    profile.office_phone = "0700 111222"
    profile.office_email = "office@example.com"
    profile.published = True
    for title, days_ago, picture in NEWS:
        session.add(
            PartyPost(
                kind=PostKind.NEWS,
                title=title,
                body=BODY,
                image_url=PICTURE.format(picture),
                published_on=today - timedelta(days=days_ago),
                published=True,
            )
        )
    title, days_ahead, venue, picture = EVENT
    session.add(
        PartyPost(
            kind=PostKind.EVENT,
            title=title,
            body=BODY,
            image_url=PICTURE.format(picture),
            event_date=today + timedelta(days=days_ahead),
            venue=venue,
            published_on=today,
            published=True,
        )
    )


async def build_aspirant(session: AsyncSession, *, password: str, today: date) -> list[SignIn]:
    """Set up an empty database as the aspirant demo and return its sign-ins."""
    if await setup.is_set_up(session):
        raise Refused("This database is already set up; the aspirant demo needs an empty one.")
    kasarani = await _kasarani(session)
    if kasarani is None:
        raise Refused("Load the reference data first: campaign-crm seed.")

    campaign = await _set_up(session, kasarani, password)
    mobilizer = await _team(session, campaign, password)
    wards = sorted(
        await session.scalars(select(Ward).where(Ward.constituency_id == kasarani.id)),
        key=lambda ward: ward.name,
    )
    await seed_ground_game(session, campaign, wards, mobilizer)
    await _site(session, campaign, today)
    await session.commit()

    return [
        SignIn(demo_email("admin"), "Site admin", "Console: logins, settings, data export"),
        SignIn(
            demo_email("candidate"), "Candidate", "the cockpit, website editor, adds mobilizers"
        ),
        SignIn(demo_email("manager"), "Campaign manager", "the full war room and the website"),
        SignIn(demo_email("mobilizer"), "Mobilizer", f"{wards[0].name} only"),
    ]
