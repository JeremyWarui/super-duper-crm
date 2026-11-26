"""The Laikipia governor demo: a county seat worked ward by ward, with five logins."""

from backend.models import PostLabel, Seat
from backend.seed.demo_aspirant import AGENDA_PICTURES, Demo
from backend.seed.demo_content import (
    DOCUMENTS,
    PICTURE,
    PORTRAIT,
    TEAM,
    UNSPLASH,
    VIDEOS,
    Content,
)

TITLE = "Aspirant for Laikipia"
CANDIDATE = "Aspirant"
# Each agenda issue: title, summary, what we will do (one step a line), why it matters (one
# paragraph a line).
AGENDA = [
    (
        "Clean water",
        "Piped water to every town and trading centre in Laikipia.",
        "Extend the Nanyuki and Nyahururu water mains into the new estates within two years.\n"
        "Fix the leaking Rumuruti line, which loses a third of the water it carries.\n"
        "Drill and equip a borehole for every dry centre the mains do not yet reach.",
        "Families outside the towns still buy water from carts at three times the town price, "
        "and pay it every single day.\n"
        "Clean, piped water is the first thing residents ask for at every ward forum, and the "
        "first thing we will deliver.",
    ),
    (
        "Jobs for young people",
        "A youth skills centre in each of the three constituencies.",
        "Open a skills centre in every constituency with the county polytechnics.\n"
        "Teach welding, electrical, plumbing, farming and digital skills local employers ask for.\n"
        "Place the first two hundred graduates on attachments in Nanyuki's hotels and farms.",
        "Most young people in Laikipia are looking for steady work, and many have skills no "
        "certificate shows.\n"
        "Twelve employers have already offered attachments; the centres connect the two.",
    ),
    (
        "Roads and drainage",
        "Feeder roads that stay open in the rainy season.",
        "Gravel the worst feeder roads in Ol-Moran, Marmanet and Sosian first.\n"
        "Join the Nyahururu town drains to the main outfall in year one.\n"
        "Grade every market road in the county before each long rains.",
        "Muddy roads cut farmers and pupils off from markets and schools for weeks every year.\n"
        "Grading the roads costs less than one season of lost harvest.",
    ),
    (
        "Safe communities",
        "Security and peace committees in every ward.",
        "Light the main market streets, starting with the ten darkest ones residents mapped.\n"
        "Fund ward peace committees from the county budget.\n"
        "Hold a monthly security forum with the police and the ranchers in each ward.",
        "Insecurity keeps families off their land and traders out of the markets.\n"
        "The lit Nanyuki market street shows what a lit street does: people trade after dark "
        "again.",
    ),
    (
        "Education",
        "An early-years place for every child in Laikipia.",
        "Finish the stalled ECDE classrooms in Igwamiti and Rumuruti.\n"
        "Widen county bursaries and run a bursary clinic in every ward each term.\n"
        "Publish every bursary award, by school and ward.",
        "Too many families cannot keep a child in secondary school.\n"
        "Bursary money exists; families need help to reach it, and the awards need to be fair "
        "and public.",
    ),
    (
        "Health care",
        "A working dispensary in every ward.",
        "Stock every ward dispensary with essential medicines.\n"
        "Open a maternity wing at Rumuruti sub-county hospital.\n"
        "Run a free health day in each ward every quarter.",
        "Mothers in the far wards still travel to Nanyuki to give birth.\n"
        "A stocked dispensary close to home saves a day's wages and, sometimes, a life.",
    ),
]
SLIDES = [
    (
        TITLE,
        "Laikipia deserves better, and we will build it together",
        "Water, jobs, roads and safe communities for all fifteen wards.",
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

SITE = {
    "slogan": "Laikipia deserves better, and we will build it together",
    "about_headline": "An engineer from Nanyuki who builds what he promises",
    "description": (
        "The aspirant grew up in Nanyuki and went to school in Nanyuki and Nyahururu. He "
        "trained as a civil engineer and has spent ten years building roads and water lines "
        "across the county.\n\n"
        "He is running for Governor of Laikipia because the towns and centres that grew "
        "fastest still wait longest for water, roads and school places. He has walked every "
        "ward and holds an open forum in each one every month."
    ),
    "manifesto_text": (
        "Our plan for Laikipia has six parts: clean water, jobs for young people, roads and "
        "drainage, safe communities, education and health care. Each one names what we will "
        "do in the first two years and how the county budget will pay for it, ward by ward. "
        "Every shilling spent will be published on this website."
    ),
    "payment_instructions": (
        "Bring a contribution to the campaign office on Kenyatta Avenue, Nanyuki, Monday to "
        "Saturday, 8am to 6pm, and take a receipt. Every gift pays for the ground game only: "
        "volunteers' transport, printing and ward forums."
    ),
    "mpesa_paybill": "174379",
    "mpesa_account": "ASPIRANT",
}

NEWS = [
    {
        "title": "The aspirant opens the Laikipia campaign office",
        "days_ago": 12,
        "label": PostLabel.NEWS,
        "place": "Nanyuki",
        "author": TEAM,
        "image": PICTURE.format("GZLDAMHFU4"),
        "body": (
            "More than three hundred supporters filled Kenyatta Avenue on Saturday as the "
            "aspirant opened the campaign office in Nanyuki.\n\n"
            "The office is open from 8am to 6pm, Monday to Saturday. Anyone can walk in to "
            "volunteer, check their registration or raise an issue for the agenda."
        ),
    },
    {
        "title": "Clean water plan for Nyahururu and Rumuruti",
        "days_ago": 5,
        "label": PostLabel.STATEMENT,
        "place": "Nyahururu",
        "author": CANDIDATE,
        "author_photo": PORTRAIT,
        "reference": "LA/2026/014",
        "image": UNSPLASH.format("1740741705746-74e6f9b93b4f"),
        "body": (
            "Families on the edges of Nyahururu and Rumuruti still buy water from carts at "
            "three times the town price. That ends with us.\n\n"
            "In the first two years we will extend the Nanyuki and Nyahururu mains, fix the "
            "leaking Rumuruti line and drill a borehole for every dry centre the mains do not "
            "reach."
        ),
    },
    {
        "title": "Youth skills centre plan meets Laikipia employers",
        "days_ago": 8,
        "label": PostLabel.NEWS,
        "place": "Nanyuki",
        "author": TEAM,
        "image": UNSPLASH.format("1576830886922-02b61aee42ad"),
        "body": (
            "Twelve employers from Nanyuki's hotels, ranches and flower farms met the campaign "
            "on Tuesday to shape the youth skills centres.\n\n"
            "They asked for welding, electrical, plumbing, farming and digital skills, and "
            "offered attachments for the first two hundred graduates."
        ),
    },
    {
        "title": "Why Ol-Moran's roads close every long rains",
        "days_ago": 15,
        "label": PostLabel.OPINION,
        "place": "Ol-Moran",
        "author": CANDIDATE,
        "author_photo": PORTRAIT,
        "image": UNSPLASH.format("1735837836870-17bf7e6d2bd6"),
        "body": (
            "I have built roads for a living, so I know why Ol-Moran's roads close: they were "
            "never gravelled, and nobody grades them before the rains.\n\n"
            "Grading them costs less than one season of lost harvest. We will do it in year one."
        ),
    },
    {
        "title": "Street lights switched on in Nanyuki market",
        "days_ago": 20,
        "label": PostLabel.NEWS,
        "place": "Nanyuki",
        "author": TEAM,
        "image": UNSPLASH.format("1636814281352-cdfa309425b7"),
        "body": (
            "Traders and the Nanyuki ward peace committee walked the newly lit market street "
            "on Friday night with the campaign.\n\n"
            "The committee will map the next ten dark streets for the agenda's safe "
            "communities plan."
        ),
    },
    {
        "title": "Bursary clinic helps 140 families apply",
        "days_ago": 26,
        "label": PostLabel.NEWS,
        "place": "Igwamiti",
        "author": TEAM,
        "image": UNSPLASH.format("1632215861513-130b66fe97f4"),
        "body": (
            "Volunteers helped 140 families fill in county bursary forms in Igwamiti on "
            "Saturday.\n\nThe next clinic is in Rumuruti; see the events page for the date."
        ),
    },
]

# Title, ward, days ahead, venue, photo.
EVENTS = [
    ("Town hall at Nanyuki stadium", "Nanyuki", 9, "Nanyuki stadium", PICTURE.format("6KRBT8MYES")),
    (
        "Rumuruti bursary clinic",
        "Rumuruti Township",
        4,
        "Rumuruti social hall",
        UNSPLASH.format("1632215861513-130b66fe97f4"),
    ),
    (
        "Igwamiti health day",
        "Igwamiti",
        16,
        "Igwamiti health centre",
        UNSPLASH.format("1783408355447-b01a88767e6a"),
    ),
    (
        "Sosian youth forum",
        "Sosian",
        23,
        "Kimanjo community centre",
        PICTURE.format("HBADKDBJYU"),
    ),
]
# Title, message, to the mobilizer's ward (else the whole campaign), days ago.
ANNOUNCEMENTS = [
    (
        "Voter registration drive this Saturday",
        "Every ward team meets at its campaign point at 8am. Bring the register and the "
        "registration flyers; IEBC clerks will be at Nanyuki stadium and Nyahururu market.",
        False,
        2,
    ),
    (
        "Nanyuki door-to-door push",
        "We are ahead of target in Nanyuki. This week, visit the estates behind the market and "
        "record every contact the same day.",
        True,
        0,
    ),
]
EVENT_BODY = (
    "Come and meet the aspirant, ask your questions and hear the plan for your ward. Entry is "
    "free and everyone is welcome. Volunteers will be at the gate to register new supporters."
)

LAIKIPIA = Demo(
    county="Laikipia",
    constituency="",
    seat=Seat.GOVERNOR,
    title=TITLE,
    short_name="Aspirant",
    office="Campaign office, Kenyatta Avenue, Nanyuki",
    candidate=("Aspirant", "", "+254722100001"),
    manager=("Jeremy", "", "+254722100002"),
    mobilizer=("Dennis", "", "+254722100003"),
    coordinator=("Mary", "Wairimu", "+254722100004"),
    coordinator_constituency="Laikipia East",
    agenda=AGENDA,
    agenda_pictures=AGENDA_PICTURES,
    slides=SLIDES,
    field_wards=("Nanyuki", "Igwamiti", "Rumuruti Township", "Thingithu", "Marmanet", "Segera"),
    content=Content(
        site=SITE,
        news=NEWS,
        events=EVENTS,
        event_body=EVENT_BODY,
        # The NG-CDF Act is for an MP's seat; a county seat keeps the rest.
        documents=[d for d in DOCUMENTS if "Constituencies Development Fund" not in d[0]],
        # The first clip is about Kasarani; the IEBC clips fit any seat.
        videos=VIDEOS[1:],
        announcements=ANNOUNCEMENTS,
    ),
)
