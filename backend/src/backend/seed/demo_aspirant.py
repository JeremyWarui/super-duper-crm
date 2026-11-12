"""The aspirant demo: a set-up aspirant installation with its candidate page, team and work."""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    AgendaIssue,
    Campaign,
    CandidateProfile,
    Constituency,
    County,
    HeroSlide,
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
from backend.seed.site import BODY, PICTURE, SKILLS_PICTURE, SLIDE_PICTURES, UNSPLASH, portrait
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
# The agenda and the candidate's priorities: title, summary, what he will do, why it matters.
AGENDA = [
    (
        "Clean water",
        "Piped water to every estate in Njiru and Ruai.",
        "Extend the Ruai and Njiru mains and fix the leaking Mwiki line within two years.",
        "Families in the new estates still buy water from carts at three times the city price.",
    ),
    (
        "Jobs for young people",
        "A youth skills centre in each of the five wards.",
        "Open skills centres with the county polytechnic and link graduates to local employers.",
        "Most young people in Kasarani are looking for steady work.",
    ),
    (
        "Roads and drainage",
        "Feeder roads that stay open in the rainy season.",
        "Tarmac the worst feeder roads and clear the drains before every long rains.",
        "Flooded roads cut traders and pupils off for weeks every year.",
    ),
    (
        "Safe neighbourhoods",
        "Street lights and community policing in every ward.",
        "Light the main walkways and fund ward security committees from the NG-CDF.",
        "Dark paths after 7pm are where most evening attacks happen.",
    ),
    (
        "Education",
        "A school place for every child in Kasarani.",
        "Finish the stalled classrooms in Mwiki and Ruai and widen NG-CDF bursaries.",
        "Too many families cannot keep a child in secondary school.",
    ),
    (
        "Health care",
        "A working dispensary in every ward.",
        "Stock the ward dispensaries and open a maternity wing at Ruai health centre.",
        "Mothers in Ruai still travel to the city centre to give birth.",
    ),
]
# The candidate's priorities are the first four agenda issues.
PRIORITIES = 4
AGENDA_PICTURES = [
    UNSPLASH.format(n)
    for n in (
        "1740741705746-74e6f9b93b4f",
        SKILLS_PICTURE,
        "1735837836870-17bf7e6d2bd6",
        "1636814281352-cdfa309425b7",
        "1632215861513-130b66fe97f4",
        "1783408355447-b01a88767e6a",
    )
]
SLIDES = [
    (
        "David Otieno for Kasarani",
        "Kasarani deserves better, and we will build it together",
        "Water, jobs, roads and safe streets for all five wards.",
        "Read the agenda",
        "/agenda",
    ),
    (
        "Volunteer",
        "Join the team going door to door this month",
        "Give a Saturday morning in your own ward.",
        "Volunteer",
        "/volunteer",
    ),
    (
        "Back the campaign",
        "Every shilling goes to the ground game",
        "Contribute by M-Pesa and get a receipt the same day.",
        "Contribute",
        "/contribute",
    ),
]


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
    """Publish the candidate page, the agenda, the carousel, two news posts and an event."""
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
        {"title": title, "text": summary, "image_url": picture}
        for (title, summary, _, _), picture in zip(AGENDA, AGENDA_PICTURES, strict=True)
    ][:PRIORITIES]
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
    for n, (title, summary, what, why) in enumerate(AGENDA):
        session.add(
            AgendaIssue(
                title=title,
                summary=summary,
                what_we_will_do=what,
                why_it_matters=why,
                image_url=AGENDA_PICTURES[n],
                sort_order=n,
                published=True,
            )
        )
    for n, (kicker, headline, line, label, url) in enumerate(SLIDES):
        session.add(
            HeroSlide(
                kicker=kicker,
                headline=headline,
                line=line,
                button_label=label,
                button_url=url,
                image_url=PICTURE.format(SLIDE_PICTURES[n]),
                sort_order=n,
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
