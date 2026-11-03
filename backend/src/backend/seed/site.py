"""The demo website: a made-up party's branding, leaders, news, events and branches."""

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    AgendaIssue,
    Branch,
    County,
    HeroSlide,
    PartyDocument,
    PartyLeader,
    PartyPost,
    PartySettings,
    PostKind,
    PostLabel,
)

PHOTO = "https://randomuser.me/api/portraits/{}.jpg"
PICTURE = "https://picsum.photos/seed/pamoja-{}/1200/675"

SETTINGS = {
    "name": "Pamoja Party",
    "short_name": "PP",
    "slogan": "Pamoja tunaweza",
    "registration_number": "DEMO-001",
    "logo_url": "https://placehold.co/200x200/0b5d3b/ffffff/png?text=P",
    "primary_colour": "#0b5d3b",
    "secondary_colour": "#f2b705",
    "contact_email": "info@example.com",
    "contact_phone": "0700 000000",
    "address": "Demo House, Moi Avenue, Nairobi",
    "description": (
        "A made-up party for trying out the platform. It stands for jobs for young people, "
        "fair prices for farmers, and county services that answer to the people they serve."
    ),
    "manifesto_text": (
        "1. Jobs: a youth apprenticeship in every ward.\n"
        "2. Farmers: fair prices and cold stores in every county.\n"
        "3. Health: a staffed dispensary within 5 km of every home.\n"
        "4. Open counties: every budget line published online."
    ),
    "social_links": {"X": "https://x.com/example", "Facebook": "https://facebook.com/example"},
}

LEADERS = [
    ("Amina Wanjiru", "Party Leader", "women/44", "Former county executive for trade."),
    ("David Otieno", "Deputy Party Leader", "men/32", "Agricultural economist from Kisumu."),
    ("Grace Chebet", "Secretary General", "women/68", "Runs the party's branch network."),
    ("Joseph Mwangi", "National Treasurer", "men/75", "Accountant and co-operative organiser."),
    ("Halima Abdi", "Youth League Chair", "women/12", "Founded a youth skills hub in Garissa."),
    ("Peter Kiprono", "Organising Secretary", "men/52", "Leads voter registration drives."),
]

NEWS = [
    ("Party launches youth apprenticeship plan", 1),
    ("Recruitment drive reaches 10,000 new members", 4),
    ("National Delegates Conference dates announced", 9),
    ("Farmers' forum in Nakuru draws record turnout", 15),
]

EVENTS = [
    ("Nairobi members' town hall", 6, "KICC, Nairobi"),
    ("Kisumu youth rally", 13, "Jomo Kenyatta Grounds, Kisumu"),
    ("Mombasa coast branch meeting", 27, "Tononoka Hall, Mombasa"),
]

STATEMENTS = [
    ("Statement on the cost of living", "PP/ST/014/2026", "Grace Chebet, Secretary General", 2),
    ("Notice to aspirants: nomination timetable", "PP/EB/006/2026", "Elections Board", 6),
]

OPINIONS = [
    ("Why this election is about young people", "Amina Wanjiru", "women/44", 3),
    ("Devolution works when counties publish their budgets", "Joseph Mwangi", "men/75", 8),
]

DOCUMENTS = [
    ("Party constitution (PDF)", "https://example.com/pamoja/constitution.pdf"),
    ("Nomination rules (PDF)", "https://example.com/pamoja/nomination-rules.pdf"),
    ("Manifesto (PDF)", "https://example.com/pamoja/manifesto.pdf"),
]

BODY = (
    "This is sample text for the demo website. A real post would carry the full story: "
    "who spoke, what was agreed, and what members can do next."
)


async def seed_branches(session: AsyncSession, today: date) -> int:
    """A published dummy branch for every county that has none; returns how many were added."""
    have = set(await session.scalars(select(Branch.county_id)))
    added = 0
    for county in await session.scalars(select(County).order_by(County.name)):
        if county.id in have:
            continue
        slug = "".join(ch for ch in county.name.lower() if ch.isalnum())
        session.add(
            Branch(
                county_id=county.id,
                chairperson="Demo chairperson",
                secretary="Demo secretary",
                office_address=f"Party office, {county.name}",
                phone=SETTINGS["contact_phone"],
                email=f"{slug}@demo.pamoja.test",
                next_meeting_on=today + timedelta(days=14),
                next_meeting_venue=f"{county.name} branch office",
                published=True,
            )
        )
        added += 1
    await session.commit()
    return added


SLIDES = [
    (
        "Pamoja Party",
        "Together, we build a fairer Kenya",
        "Jobs, fair prices and services that reach every ward.",
        "Read our agenda",
        "/#issues",
    ),
    (
        "Branch meetings",
        "Your county branch meets this month",
        "Find your branch, meet its officials and have your say.",
        "Find your branch",
        "/counties",
    ),
    (
        "Youth league",
        "Young members lead our ward work",
        "Volunteer for events and mobilisation where you live.",
        "Join the party",
        "/join-party",
    ),
    (
        "Party news",
        "Statements and news from the party",
        "Read what the party said this week and why.",
        "Read the news",
        "/news",
    ),
]

ISSUES = [
    (
        "Jobs and young people",
        "Work for the young people of every county.",
        "Back county apprenticeships and small-business loans for young people.",
        "Most young Kenyans are looking for steady work.",
    ),
    (
        "Cost of living",
        "Fair prices for food, fuel and power.",
        "Review taxes on basic goods and support farmers to sell directly.",
        "Families spend most of what they earn on basics.",
    ),
    (
        "Health care",
        "A clinic within reach of every family.",
        "Staff and stock ward dispensaries, and pay health workers on time.",
        "Too many families travel far for basic care.",
    ),
    (
        "Clean governance",
        "Public money spent in the open.",
        "Publish county budgets and contracts, and audit them every year.",
        "Trust in leaders depends on how they use public money.",
    ),
]


async def seed_home(session: AsyncSession) -> int:
    """Published demo slides and agenda issues when there are none; returns how many were added."""
    added = 0
    if not await session.scalar(select(func.count()).select_from(HeroSlide)):
        for n, (kicker, headline, line, label, url) in enumerate(SLIDES):
            session.add(
                HeroSlide(
                    kicker=kicker,
                    headline=headline,
                    line=line,
                    button_label=label,
                    button_url=url,
                    image_url=PICTURE.format(f"slide-{n + 1}"),
                    sort_order=n,
                    published=True,
                )
            )
            added += 1
    if not await session.scalar(select(func.count()).select_from(AgendaIssue)):
        for n, (title, summary, what, why) in enumerate(ISSUES):
            session.add(
                AgendaIssue(
                    title=title,
                    summary=summary,
                    what_we_will_do=what,
                    why_it_matters=why,
                    sort_order=n,
                    published=True,
                )
            )
            added += 1
    await session.commit()
    return added


async def seed_site(session: AsyncSession, today: date) -> bool:
    """Brand the party and publish the demo leaders and posts; False when content already exists.

    Overwrites the party's name, branding, contacts and manifesto; for a local or demo database.
    """
    for model in (PartyLeader, PartyPost):
        if await session.scalar(select(func.count()).select_from(model)):
            return False
    settings = await session.get(PartySettings, 1) or PartySettings(id=1)
    for field, value in SETTINGS.items():
        setattr(settings, field, value)
    session.add(settings)
    for order, (name, position, photo, bio) in enumerate(LEADERS):
        session.add(
            PartyLeader(
                name=name,
                position=position,
                bio=bio,
                photo_url=PHOTO.format(photo),
                sort_order=order,
                published=True,
            )
        )
    for n, (title, days_ago) in enumerate(NEWS, 1):
        session.add(
            PartyPost(
                kind=PostKind.NEWS,
                title=title,
                body=BODY,
                image_url=PICTURE.format(f"news-{n}"),
                published_on=today - timedelta(days=days_ago),
                published=True,
            )
        )
    for n, (title, days_ahead, venue) in enumerate(EVENTS, 1):
        session.add(
            PartyPost(
                kind=PostKind.EVENT,
                title=title,
                body=BODY,
                image_url=PICTURE.format(f"event-{n}"),
                event_date=today + timedelta(days=days_ahead),
                venue=venue,
                published_on=today,
                published=True,
            )
        )
    await session.commit()
    return True


async def seed_news(session: AsyncSession, today: date) -> int:
    """Demo statements, opinion pieces, event counties and documents where none exist yet;
    returns how many rows were added or changed."""
    changed = 0
    if not await session.scalar(
        select(func.count()).select_from(PartyPost).where(PartyPost.label != PostLabel.NEWS)
    ):
        for n, (title, ref, author, days_ago) in enumerate(STATEMENTS, 1):
            session.add(
                PartyPost(
                    kind=PostKind.NEWS,
                    label=PostLabel.STATEMENT,
                    title=title,
                    body=BODY,
                    place="National",
                    author=author,
                    reference=ref,
                    pdf_url=f"https://example.com/pamoja/statement-{n}.pdf",
                    published_on=today - timedelta(days=days_ago),
                    published=True,
                )
            )
        for title, author, photo, days_ago in OPINIONS:
            session.add(
                PartyPost(
                    kind=PostKind.NEWS,
                    label=PostLabel.OPINION,
                    title=title,
                    body=BODY,
                    place="National",
                    author=author,
                    author_photo_url=PHOTO.format(photo),
                    published_on=today - timedelta(days=days_ago),
                    published=True,
                )
            )
        changed += len(STATEMENTS) + len(OPINIONS)
    counties = {c.name.split()[0]: c.id for c in await session.scalars(select(County))}
    for event in await session.scalars(
        select(PartyPost).where(PartyPost.kind == PostKind.EVENT, PartyPost.county_id.is_(None))
    ):
        town = event.venue.rsplit(",", 1)[-1].strip()
        if town in counties:
            event.county_id = counties[town]
            changed += 1
    if not await session.scalar(select(func.count()).select_from(PartyDocument)):
        for n, (title, url) in enumerate(DOCUMENTS):
            session.add(PartyDocument(title=title, url=url, sort_order=n, published=True))
        changed += len(DOCUMENTS)
    await session.commit()
    return changed
