"""The demo website: a made-up party's branding, leaders, news, events and branches."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    AgendaIssue,
    Aspirant,
    AspirantStatus,
    Branch,
    CandidateProfile,
    Constituency,
    County,
    HeroSlide,
    OrganisationType,
    PartyConsentChannel,
    PartyDocument,
    PartyLeader,
    PartyMember,
    PartyMemberStatus,
    PartyOrgan,
    PartyPost,
    PartySettings,
    PartyValue,
    PartyVideo,
    PostKind,
    PostLabel,
    PrimaryResult,
    Seat,
    SiteSettings,
    Ward,
    party_post_aspirants,
)
from backend.services.consent import PARTY_WORDING

# Official-style portraits from Unsplash (free licence), named by their image path.
_PORTRAIT = "https://images.unsplash.com/{}?w=600&h=750&fit=crop&crop=faces"
PORTRAITS = {
    "amina": "photo-1573497491207-618cc224f243",
    "david": "photo-1588178454780-441fa5b99fa5",
    "grace": "photo-1666867936058-de34bfd5b320",
    "joseph": "photo-1789972449452-b5d1009f7794",
    "halima": "photo-1666867540898-aaa1993ffabc",
    "peter": "photo-1642257859842-c95f9fa8121d",
    "mary": "photo-1700156246325-65bbb9e1dc0d",
    "brian": "photo-1616805765352-beedbad46b2a",
    "akinyi": "photo-1763757321139-e7e4de128cd9",
    "faith": "photo-1573497019418-b400bb3ab074",
}


def portrait(key: str) -> str:
    return _PORTRAIT.format(PORTRAITS[key])


# Free (CC0) StockSnap scenes, named by their StockSnap id.
PICTURE = "https://cdn.stocksnap.io/img-thumbs/960w/{}.jpg"
SLIDE_PICTURES = ["HBADKDBJYU", "X60YH1SWTF", "5TRB09XUBX", "6DWU4LVLXE", "FOMJTSRHS3"]
NEWS_PICTURES = ["GZLDAMHFU4", "6B6QMRB4XI", "ZMTW3XX4SO", "UE4PDNKNCS"]
EVENT_PICTURES = ["6KRBT8MYES", "PYULJR0I6W", "HOSIXQG6JS"]

SETTINGS = {
    "name": "Pamoja Party",
    "short_name": "PP",
    "slogan": "Pamoja tunaweza",
    "registration_number": "DEMO-001",
    "about_headline": "A party built in every ward, for every Kenyan",
    "founded_year": "2024",
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
    "aspirant_steps": (
        "Be a paid-up party member for at least six months.\n"
        "Read the nomination rules and pick the seat you will vie for.\n"
        "Apply through your account with your ID and a short statement.\n"
        "Pay the nomination fee once the Elections Board clears you.\n"
        "Campaign in the party primary under the party's code of conduct."
    ),
    "social_links": {
        "X": "https://x.com/example",
        "Facebook": "https://facebook.com/example",
        "YouTube": "https://youtube.com/@example",
    },
}
# The SETTINGS keys that live on the party settings row; the rest are site settings.
PARTY_FIELDS = {"registration_number", "founded_year", "aspirant_steps"}

LEADERS = [
    ("Amina Wanjiru", "Party Leader", "amina", "Former county executive for trade."),
    ("David Otieno", "Deputy Party Leader", "david", "Agricultural economist from Kisumu."),
    ("Grace Chebet", "Secretary General", "grace", "Runs the party's branch network."),
    ("Joseph Mwangi", "National Treasurer", "joseph", "Accountant and co-operative organiser."),
    ("Halima Abdi", "Youth League Chair", "halima", "Founded a youth skills hub in Garissa."),
    ("Peter Kiprono", "Organising Secretary", "peter", "Leads voter registration drives."),
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
    ("Why this election is about young people", "Amina Wanjiru", "amina", 3),
    ("Devolution works when counties publish their budgets", "Joseph Mwangi", "joseph", 8),
]

VALUES = [
    ("Work for every young person", "An apprenticeship or a first job within reach of every ward."),
    ("Fair prices", "Farmers paid on time and families paying less for food and fuel."),
    ("Services close to home", "A staffed clinic and a school within walking distance."),
    ("Open counties", "Every budget line published, every tender explained."),
]

ORGANS = [
    (
        "National Delegates Convention",
        "Supreme organ; elects national officials and amends the constitution.",
    ),
    ("National Executive Committee", "Runs the party between conventions; approves party lists."),
    ("National Elections Board", "Runs nominations and internal elections."),
    ("Appeals & Disputes Committee", "Hears appeals on nominations and party elections."),
]

DOCUMENTS = [
    ("Party constitution (PDF)", "https://example.com/pamoja/constitution.pdf"),
    ("Nomination rules (PDF)", "https://example.com/pamoja/nomination-rules.pdf"),
    ("Manifesto (PDF)", "https://example.com/pamoja/manifesto.pdf"),
]

VIDEOS = [
    ("Party leader's rally speech in Nakuru", "12:40", "QYPJ92FECM"),
    ("Manifesto launch highlights", "4:15", "162JMR86DU"),
    ("Town hall: questions from members", "38:02", "6A2TYWJGIL"),
]

# (name, phone, seat, area, photo, slogan, priorities); the area is a county, constituency or
# ward name by the seat.
CANDIDATES = [
    (
        "Mary Njeri",
        "+254700100001",
        Seat.GOVERNOR,
        "Nakuru",
        "mary",
        "A county that works for farmers",
        ["Cold stores in every sub-county", "Fair maize prices"],
    ),
    (
        "Brian Ochieng",
        "+254700100002",
        Seat.MP,
        "Westlands",
        "brian",
        "Jobs for Westlands youth",
        ["A skills hub in every ward", "Safer streets at night"],
    ),
    (
        "Akinyi Odhiambo",
        "+254700100003",
        Seat.MP,
        "Kisumu Central",
        "akinyi",
        "Kisumu rising",
        ["Clean water for every estate", "Lakefront jobs"],
    ),
    (
        "Faith Muthoni",
        "+254700100004",
        Seat.MCA,
        "Kileleshwa",
        "faith",
        "Your ward, your voice",
        ["Open ward budgets", "Street lights on every road"],
    ),
]

# (seat, area, days before today it was declared or None while counting, candidates)
RESULTS = [
    (Seat.GOVERNOR, "Nakuru County", 6, [("Mary Njeri", 18_402), ("Samuel Korir", 15_960)]),
    (Seat.MP, "Westlands", 5, [("Brian Ochieng", 6_215), ("Lucy Wairimu", 4_870)]),
    (Seat.MP, "Kisumu Central", 5, [("Akinyi Odhiambo", 7_034), ("Tom Ouma", 3_112)]),
    (Seat.MCA, "Kileleshwa", None, [("Faith Muthoni", 812), ("Ali Hassan", 774)]),
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
                    image_url=PICTURE.format(SLIDE_PICTURES[n % len(SLIDE_PICTURES)]),
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

    Overwrites the site's name, branding, contacts and manifesto; for a local or demo database.
    """
    for model in (PartyLeader, PartyPost):
        if await session.scalar(select(func.count()).select_from(model)):
            return False
    site = await session.get(SiteSettings, 1) or SiteSettings(
        id=1, organisation_type=OrganisationType.PARTY
    )
    party = await session.get(PartySettings, 1) or PartySettings(id=1)
    for field, value in SETTINGS.items():
        setattr(party if field in PARTY_FIELDS else site, field, value)
    session.add_all([site, party])
    for order, (name, position, photo, bio) in enumerate(LEADERS):
        session.add(
            PartyLeader(
                name=name,
                position=position,
                bio=bio,
                photo_url=portrait(photo),
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
                image_url=PICTURE.format(NEWS_PICTURES[n % len(NEWS_PICTURES)]),
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
                image_url=PICTURE.format(EVENT_PICTURES[n % len(EVENT_PICTURES)]),
                event_date=today + timedelta(days=days_ahead),
                venue=venue,
                published_on=today,
                published=True,
            )
        )
    await session.commit()
    return True


async def seed_news(session: AsyncSession, today: date) -> int:
    """Demo statements, opinion pieces, event counties and About-page content where none exist yet;
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
                    author_photo_url=portrait(photo),
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
    site = await session.get(SiteSettings, 1)
    party = await session.get(PartySettings, 1)
    for row, fields in (
        (site, ("slogan", "about_headline")),
        (party, ("registration_number", "founded_year", "aspirant_steps")),
    ):
        for field in fields if row is not None else ():
            if not getattr(row, field):
                setattr(row, field, SETTINGS[field])
                changed += 1
    for model, rows in ((PartyValue, VALUES), (PartyOrgan, ORGANS)):
        if not await session.scalar(select(func.count()).select_from(model)):
            for n, (title, text) in enumerate(rows):
                session.add(model(title=title, text=text, sort_order=n, published=True))
            changed += len(rows)
    if not await session.scalar(select(func.count()).select_from(PartyDocument)):
        for n, (title, url) in enumerate(DOCUMENTS):
            session.add(PartyDocument(title=title, url=url, sort_order=n, published=True))
        changed += len(DOCUMENTS)
    if not await session.scalar(select(func.count()).select_from(PartyVideo)):
        for n, (title, duration, picture) in enumerate(VIDEOS):
            session.add(
                PartyVideo(
                    title=title,
                    url=f"https://example.com/pamoja/video-{n + 1}",
                    thumbnail_url=PICTURE.format(picture),
                    duration=duration,
                    sort_order=n,
                    published=True,
                )
            )
        changed += len(VIDEOS)
    changed += await _seed_candidates(session, today)
    if not await session.scalar(select(func.count()).select_from(PrimaryResult)):
        for seat, area, days_ago, candidates in RESULTS:
            declared = None if days_ago is None else today - timedelta(days=days_ago)
            for name, votes in candidates:
                session.add(
                    PrimaryResult(
                        seat=seat,
                        area=area,
                        candidate=name,
                        votes=votes,
                        declared_on=declared,
                        demo=True,
                        published=True,
                    )
                )
                changed += 1
    await session.commit()
    return changed


async def _place(session: AsyncSession, seat: Seat, name: str) -> dict | None:
    """The aspirant's area columns for `name`, and a ward for its member; None if not loaded."""
    if seat is Seat.MCA:
        ward = await session.scalar(select(Ward).where(Ward.name == name).limit(1))
        return ward and {"ward_id": ward.id, "_ward": ward.id}
    if seat is Seat.MP:
        place = await session.scalar(select(Constituency).where(Constituency.name == name).limit(1))
        ward = place and await session.scalar(
            select(Ward.id).where(Ward.constituency_id == place.id).limit(1)
        )
        return place and ward and {"constituency_id": place.id, "_ward": ward}
    county = await session.scalar(select(County).where(County.name.startswith(name)).limit(1))
    ward = county and await session.scalar(
        select(Ward.id)
        .join(Constituency, Constituency.id == Ward.constituency_id)
        .where(Constituency.county_id == county.id)
        .limit(1)
    )
    return county and ward and {"county_id": county.id, "_ward": ward}


async def _seed_candidates(session: AsyncSession, today: date) -> int:
    """Demo aspirants with published profiles, the first named by the next demo event."""
    if await session.scalar(select(func.count()).select_from(CandidateProfile)):
        return 0
    made = []
    for name, phone, seat, area, photo, slogan, priorities in CANDIDATES:
        place = await _place(session, seat, area)
        if place is None or await session.scalar(
            select(PartyMember.id).where(PartyMember.phone == phone)
        ):
            continue
        member = PartyMember(
            full_name=name,
            first_name=name.split()[0],
            phone=phone,
            ward_id=place.pop("_ward"),
            status=PartyMemberStatus.APPROVED,
            consent_wording=PARTY_WORDING[PartyConsentChannel.WEB_FORM],
            consent_channel=PartyConsentChannel.WEB_FORM,
            consent_at=datetime.now(UTC),
        )
        session.add(member)
        await session.flush()
        aspirant = Aspirant(member_id=member.id, seat=seat, status=AspirantStatus.APPROVED, **place)
        session.add(aspirant)
        await session.flush()
        session.add(
            CandidateProfile(
                aspirant_id=aspirant.id,
                photo_url=portrait(photo),
                slogan=slogan,
                bio=f"{name} is a demo aspirant. " + BODY,
                priorities=[{"title": t, "text": ""} for t in priorities],
                office_address=f"Campaign office, {area}",
                office_phone=SETTINGS["contact_phone"],
                published=True,
            )
        )
        made.append(aspirant.id)
    event = await session.scalar(
        select(PartyPost.id)
        .where(PartyPost.kind == PostKind.EVENT, PartyPost.event_date >= today)
        .order_by(PartyPost.event_date)
        .limit(1)
    )
    if made and event:
        await session.execute(
            insert(party_post_aspirants), [{"post_id": event, "aspirant_id": made[0]}]
        )
    return len(made)
