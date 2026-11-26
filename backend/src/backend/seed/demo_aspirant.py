"""The demo installs: a set-up installation with its candidate page, team and work."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    AgendaIssue,
    Campaign,
    CandidateProfile,
    Constituency,
    County,
    HeroSlide,
    Seat,
    User,
    UserRole,
    Ward,
)
from backend.schemas.setup import InvitedLogin, SetupRequest, SetupSeat, SetupSite, SetupSuperuser
from backend.schemas.team import AreaWrite
from backend.security import hash_password
from backend.seed.demo import demo_email, seed_ground_game
from backend.seed.demo_content import KASARANI as KASARANI_SITE
from backend.seed.demo_content import PICTURE, PORTRAIT, UNSPLASH, Content, announce, fill_site
from backend.seed.sign_ins import SignIn
from backend.services import setup
from backend.services.accounts import add_member, new_login
from backend.services.errors import Refused
from backend.services.rich_text import from_plain
from backend.services.team import set_areas

SLIDE_PICTURES = ["HBADKDBJYU", "X60YH1SWTF", "5TRB09XUBX"]

COUNTY = "Nairobi City"
CONSTITUENCY = "Kasarani"
TITLE = "David Otieno for Kasarani"
# The agenda and the candidate's priorities: title, summary, what he will do (one step a line),
# why it matters (one paragraph a line).
AGENDA = [
    (
        "Clean water",
        "Piped water to every estate in Njiru and Ruai.",
        "Extend the Ruai and Njiru water mains into the new estates within two years.\n"
        "Fix the leaking Mwiki line, which loses a third of the water it carries.\n"
        "Put a public water point in every estate the mains do not yet reach.",
        "Families in the new estates still buy water from carts at three times the city price, "
        "and pay it every single day.\n"
        "Clean, piped water is the first thing residents ask for at every ward forum, and the "
        "first thing we will deliver.",
    ),
    (
        "Jobs for young people",
        "A youth skills centre in each of the five wards.",
        "Open a skills centre in every ward with the county polytechnic.\n"
        "Teach welding, electrical, plumbing and digital skills that local employers ask for.\n"
        "Place the first two hundred graduates on attachments in Ruaraka and Baba Dogo.",
        "Most young people in Kasarani are looking for steady work, and many have skills no "
        "certificate shows.\n"
        "Twelve employers have already offered attachments; the centres connect the two.",
    ),
    (
        "Roads and drainage",
        "Feeder roads that stay open in the rainy season.",
        "Tarmac the worst feeder roads in Njiru, Ruai and Clay City first.\n"
        "Join the Clay City drains to the main outfall in year one.\n"
        "Clear every drain in the constituency before each long rains.",
        "Flooded roads cut traders and pupils off for weeks every year.\n"
        "Joining the drains costs less than one season of lost trade.",
    ),
    (
        "Safe neighbourhoods",
        "Street lights and community policing in every ward.",
        "Light the main walkways, starting with the ten darkest paths residents mapped.\n"
        "Fund ward security committees from the NG-CDF.\n"
        "Hold a monthly safety forum with the police in each ward.",
        "Dark paths after 7pm are where most evening attacks happen.\n"
        "The Ruai walkway lights show what a lit path does: people walk home again.",
    ),
    (
        "Education",
        "A school place for every child in Kasarani.",
        "Finish the stalled classrooms in Mwiki and Ruai.\n"
        "Widen NG-CDF bursaries and run a bursary clinic in every ward each term.\n"
        "Publish every bursary award, by school and ward.",
        "Too many families cannot keep a child in secondary school.\n"
        "Bursary money exists; families need help to reach it, and the awards need to be fair "
        "and public.",
    ),
    (
        "Health care",
        "A working dispensary in every ward.",
        "Stock every ward dispensary with essential medicines.\n"
        "Open a maternity wing at Ruai health centre.\n"
        "Run a free health day in each ward every quarter.",
        "Mothers in Ruai still travel to the city centre to give birth.\n"
        "A stocked dispensary close to home saves a day's wages and, sometimes, a life.",
    ),
]
# The candidate's priorities are the first three agenda issues, as many as a profile holds.
PRIORITIES = 3
AGENDA_PICTURES = [
    UNSPLASH.format(n)
    for n in (
        "1740741705746-74e6f9b93b4f",
        "1576830886922-02b61aee42ad",
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


# A login: first name, last name, phone.
Person = tuple[str, str, str]


@dataclass(frozen=True)
class Demo:
    """One demo install: its seat, team, agenda, carousel and website."""

    county: str
    # Blank for a county seat.
    constituency: str
    seat: Seat
    title: str
    short_name: str
    office: str
    candidate: Person
    manager: Person
    mobilizer: Person
    agenda: list[tuple[str, str, str, str]]
    agenda_pictures: list[str]
    slides: list[tuple[str, str, str, str, str]]
    content: Content
    # A coordinator and the constituency they cover, when the demo has one.
    coordinator: Person | None = None
    coordinator_constituency: str = ""
    # The wards the ground game works, the mobilizer's first; blank works every ward of the seat.
    field_wards: tuple[str, ...] = ()
    # Contacts in each worked ward; half the field wards are worked.
    contacts_per_ward: int = 4


KASARANI = Demo(
    county=COUNTY,
    constituency=CONSTITUENCY,
    seat=Seat.MP,
    title=TITLE,
    short_name="Otieno",
    office="Campaign office, Mwiki Road, Kasarani",
    candidate=("David", "Otieno", "+254722000001"),
    manager=("Lucy", "Wambui", "+254722000002"),
    mobilizer=("Kevin", "Ochieng", "+254722000003"),
    agenda=AGENDA,
    agenda_pictures=AGENDA_PICTURES,
    slides=SLIDES,
    content=KASARANI_SITE,
)


async def _seat_area(
    session: AsyncSession, demo: Demo
) -> tuple[County | None, Constituency | None]:
    county = await session.scalar(select(County).where(County.name == demo.county))
    if county is None or not demo.constituency:
        return county, None
    constituency = await session.scalar(
        select(Constituency).where(
            Constituency.county_id == county.id, Constituency.name == demo.constituency
        )
    )
    return county, constituency


async def _set_up(
    session: AsyncSession,
    demo: Demo,
    county: County,
    constituency: Constituency | None,
    password: str,
) -> Campaign:
    """The first-run setup as /setup runs it: the seat and the candidate login."""
    token = await setup.new_token(session)
    first, last, phone = demo.candidate
    result = await setup.run(
        session,
        SetupRequest(
            token=token,
            site=SetupSite(
                name=demo.title,
                short_name=demo.short_name,
                primary_colour="#0b5d3b",
                secondary_colour="#f2b705",
                contact_email="office@example.com",
                contact_phone="0700 111222",
                address=demo.office,
            ),
            superuser=SetupSuperuser(
                username="admin",
                email=demo_email("admin"),
                password=password,
                first_name="Kevin",
                last_name="Mwangi",
            ),
            campaign=SetupSeat(
                title=demo.title,
                seat=demo.seat,
                election_date=date(2027, 8, 10),
                county=None if constituency else county.id,
                constituency=constituency.id if constituency else None,
                candidate=InvitedLogin(
                    username="candidate",
                    email=demo_email("candidate"),
                    first_name=first,
                    last_name=last,
                    phone=phone,
                ),
            ),
        ),
    )
    campaign = await session.get(Campaign, result.workspace)
    candidate = await session.scalar(select(User).where(User.username == "candidate"))
    candidate.password_hash = hash_password(password)
    return campaign


async def _login(
    session: AsyncSession, username: str, role: UserRole, person: Person, password: str
) -> User:
    first, last, phone = person
    user, _ = await new_login(
        session,
        username=username,
        role=role,
        password=password,
        email=demo_email(username),
        first_name=first,
        last_name=last,
        phone=phone,
    )
    return user


async def _team(session: AsyncSession, campaign: Campaign, demo: Demo, password: str) -> User:
    """The manager and any coordinator on the campaign; returns the mobilizer login the ground
    game places."""
    manager = await _login(session, "manager", UserRole.MANAGER, demo.manager, password)
    await add_member(session, campaign.id, manager)
    if demo.coordinator:
        coordinator = await _login(
            session, "coordinator", UserRole.COORDINATOR, demo.coordinator, password
        )
        await add_member(session, campaign.id, coordinator)
        area = await session.scalar(
            select(Constituency.id).where(
                Constituency.county_id == campaign.county_id,
                Constituency.name == demo.coordinator_constituency,
            )
        )
        await set_areas(
            session, campaign, coordinator.id, AreaWrite(constituencies=[area]), actor=manager
        )
    return await _login(session, "mobilizer", UserRole.MOBILIZER, demo.mobilizer, password)


async def _site(session: AsyncSession, campaign: Campaign, demo: Demo, today: date) -> None:
    """Publish the candidate page, the agenda, the carousel and the rest of the website."""
    profile = await session.scalar(
        select(CandidateProfile).where(CandidateProfile.campaign_id == campaign.id)
    )
    profile.photo_url = PORTRAIT
    profile.slogan = demo.content.site["slogan"]
    profile.bio = from_plain(demo.content.site["description"])
    profile.priorities = [
        {"title": title, "text": summary, "image_url": picture}
        for (title, summary, _, _), picture in zip(demo.agenda, demo.agenda_pictures, strict=True)
    ][:PRIORITIES]
    profile.office_address = demo.office
    profile.office_phone = "0700 111222"
    profile.office_email = "office@example.com"
    profile.published = True
    for n, (title, summary, what, why) in enumerate(demo.agenda):
        session.add(
            AgendaIssue(
                title=title,
                summary=summary,
                what_we_will_do=what,
                why_it_matters=why,
                image_url=demo.agenda_pictures[n],
                sort_order=n,
                published=True,
            )
        )
    for n, (kicker, headline, line, label, url) in enumerate(demo.slides):
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
    await fill_site(session, campaign, today, demo.content)


async def _field_wards(
    session: AsyncSession, demo: Demo, county: County, constituency: Constituency | None
) -> list[Ward]:
    if constituency is not None:
        found = select(Ward).where(Ward.constituency_id == constituency.id)
    else:
        found = select(Ward).join(Constituency).where(Constituency.county_id == county.id)
    wards = {ward.name: ward for ward in await session.scalars(found)}
    return [wards[name] for name in demo.field_wards or sorted(wards)]


async def build_aspirant(
    session: AsyncSession, *, password: str, today: date, demo: Demo = KASARANI
) -> list[SignIn]:
    """Set up an empty database as the demo and return its sign-ins."""
    if await setup.is_set_up(session):
        raise Refused("This database is already set up; the demo needs an empty one.")
    county, constituency = await _seat_area(session, demo)
    if county is None or (demo.constituency and constituency is None):
        raise Refused("Load the reference data first: campaign-crm seed.")

    campaign = await _set_up(session, demo, county, constituency, password)
    mobilizer = await _team(session, campaign, demo, password)
    wards = await _field_wards(session, demo, county, constituency)
    await seed_ground_game(session, campaign, wards, mobilizer, demo.contacts_per_ward)
    await _site(session, campaign, demo, today)
    await session.commit()
    manager = await session.scalar(select(User).where(User.username == "manager"))
    await announce(session, campaign, manager, wards[0], demo.content)

    sign_ins = [
        SignIn(demo_email("admin"), "Site admin", "Console: logins, settings, data export"),
        SignIn(
            demo_email("candidate"), "Candidate", "the cockpit, website editor, adds mobilizers"
        ),
        SignIn(demo_email("manager"), "Campaign manager", "the full war room and the website"),
    ]
    if demo.coordinator:
        sign_ins.append(
            SignIn(
                demo_email("coordinator"),
                "Coordinator",
                f"{demo.coordinator_constituency} only: its wards, mobilizers and calls",
            )
        )
    sign_ins.append(SignIn(demo_email("mobilizer"), "Mobilizer", f"{wards[0].name} only"))
    return sign_ins
