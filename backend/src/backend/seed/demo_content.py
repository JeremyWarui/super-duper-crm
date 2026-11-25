"""The aspirant demo's website content: news, events, documents, videos and the site settings."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Campaign,
    Document,
    Event,
    Notice,
    Post,
    PostKind,
    PostLabel,
    SiteSettings,
    User,
    Video,
    Ward,
)
from backend.services import announcements
from backend.services.content import slug_of
from backend.services.rich_text import from_plain

# Free (CC0) StockSnap scenes, named by their StockSnap id.
PICTURE = "https://cdn.stocksnap.io/img-thumbs/960w/{}.jpg"
# Free Unsplash photos, named by their Unsplash id.
UNSPLASH = "https://images.unsplash.com/photo-{}?w=900&q=75&auto=format&fit=crop"
PORTRAIT = (
    "https://images.unsplash.com/photo-1588178454780-441fa5b99fa5?w=600&h=750&fit=crop&crop=faces"
)
CANDIDATE = "David Otieno"
TEAM = "Campaign team"

SITE = {
    "slogan": "Kasarani deserves better, and we will build it together",
    "about_headline": "An engineer from Mwiki who builds what he promises",
    "description": (
        "David Otieno grew up in Mwiki and went to Kasarani primary and Ruaraka high school. He "
        "trained as a civil engineer at the University of Nairobi and has spent ten years "
        "building roads and water lines across Nairobi, including the Njiru water main.\n\n"
        "He is running for Member of Parliament for Kasarani because the estates that grew "
        "fastest, Njiru, Ruai and Clay City, still wait longest for water, roads and school "
        "places. He has walked every ward and holds an open forum in each one every month."
    ),
    "manifesto_text": (
        "Our plan for Kasarani has six parts: clean water, jobs for young people, roads and "
        "drainage, safe neighbourhoods, education and health care. Each one names what we will "
        "do in the first two years and how the NG-CDF will pay for it, ward by ward. Every "
        "shilling spent will be published on this website."
    ),
    "payment_instructions": (
        "Bring a contribution to the campaign office on Mwiki Road, Kasarani, Monday to "
        "Saturday, 8am to 6pm, and take a receipt. Every gift pays for the ground game only: "
        "volunteers' transport, printing and ward forums."
    ),
    "mpesa_paybill": "174379",
    "mpesa_account": "OTIENO",
}

NEWS = [
    {
        "title": "David Otieno opens his Kasarani campaign office",
        "days_ago": 12,
        "label": PostLabel.NEWS,
        "place": "Mwiki",
        "author": TEAM,
        "image": PICTURE.format("GZLDAMHFU4"),
        "body": (
            "More than three hundred supporters filled Mwiki Road on Saturday as David Otieno "
            "opened the campaign office.\n\n"
            "The office is open from 8am to 6pm, Monday to Saturday. Anyone can walk in to "
            "volunteer, check their registration or raise an issue for the agenda."
        ),
    },
    {
        "title": "Clean water plan for Njiru and Ruai",
        "days_ago": 5,
        "label": PostLabel.STATEMENT,
        "place": "Njiru",
        "author": CANDIDATE,
        "author_photo": PORTRAIT,
        "reference": "DO/2026/014",
        "image": UNSPLASH.format("1740741705746-74e6f9b93b4f"),
        "body": (
            "Families in the new estates of Njiru and Ruai still buy water from carts at three "
            "times the city price. That ends with us.\n\n"
            "In the first two years we will extend the Ruai and Njiru mains, fix the leaking "
            "Mwiki line and put a public water point in every estate the mains do not reach."
        ),
    },
    {
        "title": "Youth skills centre plan meets Kasarani employers",
        "days_ago": 8,
        "label": PostLabel.NEWS,
        "place": "Kasarani",
        "author": TEAM,
        "image": UNSPLASH.format("1576830886922-02b61aee42ad"),
        "body": (
            "Twelve employers from the Ruaraka and Baba Dogo industrial areas met the campaign "
            "on Tuesday to shape the youth skills centres.\n\n"
            "They asked for welding, electrical, plumbing and digital skills, and offered "
            "attachments for the first two hundred graduates."
        ),
    },
    {
        "title": "Why Clay City floods every long rains",
        "days_ago": 15,
        "label": PostLabel.OPINION,
        "place": "Clay City",
        "author": CANDIDATE,
        "author_photo": PORTRAIT,
        "image": UNSPLASH.format("1735837836870-17bf7e6d2bd6"),
        "body": (
            "I have built drains for a living, so I know why Clay City floods: the drains were "
            "never joined to the main outfall, and nobody clears them before the rains.\n\n"
            "Joining them costs less than one season of lost trade. We will do it in year one."
        ),
    },
    {
        "title": "Street lights switched on along the Ruai walkway",
        "days_ago": 20,
        "label": PostLabel.NEWS,
        "place": "Ruai",
        "author": TEAM,
        "image": UNSPLASH.format("1636814281352-cdfa309425b7"),
        "body": (
            "Residents and the Ruai ward security committee walked the new lit path on Friday "
            "night with the campaign.\n\n"
            "The committee will map the next ten dark paths for the agenda's safe "
            "neighbourhoods plan."
        ),
    },
    {
        "title": "Bursary clinic helps 140 families apply",
        "days_ago": 26,
        "label": PostLabel.NEWS,
        "place": "Mwiki",
        "author": TEAM,
        "image": UNSPLASH.format("1632215861513-130b66fe97f4"),
        "body": (
            "Volunteers helped 140 families fill in NG-CDF bursary forms at Mwiki primary on "
            "Saturday.\n\nThe next clinic is in Njiru; see the events page for the date."
        ),
    },
]

# The campaign's events put on the website: title, ward, days ahead, venue, photo.
EVENTS = [
    ("Town hall at Mwiki grounds", "Mwiki", 9, "Mwiki grounds", PICTURE.format("6KRBT8MYES")),
    (
        "Njiru bursary clinic",
        "Njiru",
        4,
        "Njiru social hall",
        UNSPLASH.format("1632215861513-130b66fe97f4"),
    ),
    (
        "Ruai health day",
        "Ruai",
        16,
        "Ruai health centre",
        UNSPLASH.format("1783408355447-b01a88767e6a"),
    ),
    (
        "Clay City youth forum",
        "Clay City",
        23,
        "Clay City community centre",
        PICTURE.format("HBADKDBJYU"),
    ),
]
# Events start at 10am Nairobi time.
EVENT_HOUR_UTC = 7
EVENT_BODY = (
    "Come and meet David Otieno, ask your questions and hear the plan for your ward. Entry is "
    "free and everyone is welcome. Volunteers will be at the gate to register new supporters."
)

# Public documents, checked to serve a PDF.
DOCUMENTS = [
    (
        "The Constitution of Kenya, 2010",
        "https://www.constituteproject.org/constitution/Kenya_2010.pdf",
    ),
    (
        "National Government Constituencies Development Fund Act (as amended 2023)",
        "https://ngcdf.go.ke/wp-content/uploads/2023/10/new-NGCDF-Act-As-Amended-in-2022-2023.pdf",
    ),
    ("IEBC voter education curriculum", "https://www.iebc.or.ke/uploads/resources/oqwLzhwU42.pdf"),
    (
        "IEBC voter education training manual",
        "https://www.iebc.or.ke/uploads/resources/pdQMe3WKeV.pdf",
    ),
]

# Public YouTube clips, checked through YouTube's oEmbed; titles as published.
VIDEOS = [
    ("Nairobi new boom areas: Njiru, Mwiki and Clay City, Kasarani", "8W_OERfyb20"),
    ("How biometric voter registration works (IEBC)", "2icgT2MMDLE"),
    ("IEBC steps up voter education ahead of 2027", "0NubwTArc24"),
]


async def fill_site(session: AsyncSession, campaign: Campaign, today: date) -> None:
    """Fill the site settings, publish the news, documents and videos, and put the campaign's
    public events on the website."""
    wards = dict(
        (
            await session.execute(
                select(Ward.name, Ward.id).where(Ward.constituency_id == campaign.constituency_id)
            )
        ).all()
    )
    site = await session.scalar(select(SiteSettings))
    for field, value in SITE.items():
        setattr(site, field, value)
    for item in NEWS:
        session.add(
            Post(
                kind=PostKind.NEWS,
                title=item["title"],
                slug=slug_of(item["title"]),
                body=from_plain(item["body"]),
                image_url=item["image"],
                label=item["label"],
                place=item["place"],
                author=item["author"],
                author_photo_url=item.get("author_photo", ""),
                reference=item.get("reference", ""),
                published_on=today - timedelta(days=item["days_ago"]),
                published=True,
            )
        )
    for title, ward_name, days_ahead, venue, picture in EVENTS:
        day = today + timedelta(days=days_ahead)
        session.add(
            Event(
                campaign_id=campaign.id,
                ward_id=wards[ward_name],
                title=title,
                venue=venue,
                scheduled_date=datetime(day.year, day.month, day.day, EVENT_HOUR_UTC, tzinfo=UTC),
                published=True,
                description=EVENT_BODY,
                image_url=picture,
            )
        )
    for n, (title, url) in enumerate(DOCUMENTS):
        session.add(Document(title=title, url=url, sort_order=n, published=True))
    for n, (title, video_id) in enumerate(VIDEOS):
        session.add(
            Video(
                title=title,
                url=f"https://www.youtube.com/watch?v={video_id}",
                sort_order=n,
                published=True,
            )
        )


# The manager's announcements: title, message, to one ward (else the whole campaign), days ago.
ANNOUNCEMENTS = [
    (
        "Voter registration drive this Saturday",
        "Every ward team meets at its campaign point at 8am. Bring the register and the "
        "registration flyers; IEBC clerks will be at Mwiki grounds and Ruai market.",
        False,
        2,
    ),
    (
        "Clay City door-to-door push",
        "We are ahead of target in Clay City. This week, visit the estates behind the "
        "community centre and record every contact the same day.",
        True,
        0,
    ),
]


async def announce(session: AsyncSession, campaign: Campaign, manager: User, ward: Ward) -> None:
    """Send the demo announcements; the candidate has read the oldest one."""
    candidate = await session.scalar(select(User).where(User.username == "candidate"))
    now = datetime.now(UTC)
    for title, body, to_ward, days_ago in ANNOUNCEMENTS:
        sent, _ = await announcements.send(
            session, campaign.id, title, body, ward.id if to_ward else None, None, actor=manager
        )
        sent.created_at = now - timedelta(days=days_ago, hours=3)
        await session.execute(
            update(Notice)
            .where(Notice.announcement_id == sent.id)
            .values(created_at=sent.created_at)
        )
        if days_ago:
            await session.execute(
                update(Notice)
                .where(Notice.announcement_id == sent.id, Notice.user_id == candidate.id)
                .values(read_at=sent.created_at + timedelta(hours=1))
            )
    await session.commit()
