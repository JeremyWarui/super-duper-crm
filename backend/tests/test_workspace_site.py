"""The website of an aspirant installation, edited from its workspace under `site.write`."""

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AuditEvent, OrganisationType, UserRole
from backend.services.accounts import add_member
from tests.conftest import World
from tests.factories import auth, make_user, sign_in, site_settings

pytestmark = pytest.mark.parametrize(
    "organisation_type", [OrganisationType.ASPIRANT], indirect=True
)

URL = "/api/workspace/site/"


async def _login(
    session: AsyncSession, client: httpx.AsyncClient, world: World, role: UserRole
) -> dict[str, str]:
    user = await make_user(session, username=role.value, role=role)
    await add_member(session, world.campaign.id, user)
    await session.commit()
    return auth(await sign_in(client, role.value))


@pytest.fixture
async def comms(session: AsyncSession, client: httpx.AsyncClient, world: World) -> dict:
    session.add(site_settings(organisation_type=OrganisationType.ASPIRANT, name="Jane 2027"))
    await session.commit()
    return await _login(session, client, world, UserRole.COMMS)


async def test_comms_edits_posts_and_hero_slides_and_every_edit_is_audited(
    session: AsyncSession, client: httpx.AsyncClient, comms: dict
) -> None:
    post = await client.post(
        f"{URL}posts/",
        headers=comms,
        json={"kind": "news", "title": "Town hall", "published": True},
    )
    slide = await client.post(f"{URL}slides/", headers=comms, json={"headline": "Vote Jane"})
    renamed = await client.patch(
        f"{URL}slides/{slide.json()['id']}/", headers=comms, json={"headline": "Jane for MP"}
    )
    listed = await client.get(f"{URL}posts/", headers=comms)
    public = await client.get("/api/party/posts/?kind=news")
    removed = await client.delete(f"{URL}posts/{post.json()['id']}/", headers=comms)
    actions = set(await session.scalars(select(AuditEvent.action)))

    assert (post.status_code, slide.status_code, renamed.status_code) == (201, 201, 200)
    assert renamed.json()["headline"] == "Jane for MP"
    assert [p["title"] for p in listed.json()] == ["Town hall"]
    assert [p["title"] for p in public.json()] == ["Town hall"]
    assert removed.status_code == 204
    assert {
        "party.post.create",
        "party.post.delete",
        "party.hero_slide.create",
        "party.hero_slide.update",
    } <= actions


def _settings(**overrides) -> dict:
    return {
        "name": "Jane 2027",
        "primary_colour": "#1f2937",
        "secondary_colour": "#f59e0b",
        **overrides,
    }


async def test_a_colour_failing_the_contrast_check_is_refused(
    client: httpx.AsyncClient, comms: dict
) -> None:
    kept = await client.put(f"{URL}settings/", headers=comms, json=_settings(slogan="Hope"))
    pale = await client.put(
        f"{URL}settings/", headers=comms, json=_settings(primary_colour="#fafafa")
    )
    read = await client.get(f"{URL}settings/", headers=comms)

    assert (kept.status_code, kept.json()["slogan"]) == (200, "Hope")
    assert pale.status_code == 400
    assert read.json()["primary_colour"] == "#1f2937"


@pytest.mark.parametrize("role", [UserRole.COORDINATOR, UserRole.AGENT])
async def test_a_role_without_site_write_gets_403(
    session: AsyncSession, client: httpx.AsyncClient, world: World, comms: dict, role: UserRole
) -> None:
    head = await _login(session, client, world, role)

    answers = [
        (await client.get(f"{URL}posts/", headers=head)).status_code,
        (await client.post(f"{URL}slides/", headers=head, json={"headline": "x"})).status_code,
        (await client.get(f"{URL}settings/", headers=world.headers("mobilizer"))).status_code,
    ]

    assert answers == [403, 403, 403]


async def test_the_homepage_shows_the_candidate_page_once_published_and_signs_volunteers_up(
    session: AsyncSession, client: httpx.AsyncClient, world: World, comms: dict
) -> None:
    from backend.models import VolunteerProfile, WorkspaceKind

    world.campaign.kind = WorkspaceKind.STANDALONE
    await session.commit()
    page = {"slogan": "Roysambu first", "bio": "Teacher.", "published": False}
    draft = await client.put(f"{URL}candidate/", headers=comms, json=page)
    hidden = await client.get("/api/site/candidate/")
    await client.put(f"{URL}candidate/", headers=comms, json={**page, "published": True})
    shown = await client.get("/api/site/candidate/")
    joined = await client.post(
        "/api/site/volunteer/",
        json={
            "first_name": "Wanjiku",
            "last_name": "Njeri",
            "email": "wanjiku@example.com",
            "phone": "0712 345678",
            "ward": str(world.ward.id),
            "registration_centre": str(world.centre.id),
            "profession": "teacher",
            "areas": ["door_to_door"],
            "preferred_contact": "sms",
            "consent_given": True,
        },
    )
    volunteer = await session.scalar(select(VolunteerProfile))

    assert (draft.status_code, hidden.status_code) == (200, 404)
    assert (shown.json()["slogan"], shown.json()["seat"]) == ("Roysambu first", "mp")
    assert {w["name"] for w in shown.json()["wards"]} == {"Zimmerman", "Githurai"}
    assert joined.status_code == 201
    assert volunteer.campaign_id == world.campaign.id


async def test_the_contribute_page_reads_the_payment_instructions_from_the_settings(
    client: httpx.AsyncClient, comms: dict
) -> None:
    saved = await client.put(
        f"{URL}settings/", headers=comms, json=_settings(payment_instructions="Paybill 123456")
    )
    public = await client.get("/api/site/")

    assert saved.status_code == 200
    assert public.json()["payment_instructions"] == "Paybill 123456"


async def test_the_news_sign_up_shows_and_records_the_campaigns_wording(
    session: AsyncSession, client: httpx.AsyncClient, comms: dict
) -> None:
    from backend.models import Subscriber
    from backend.services.consent import CAMPAIGN_SUBSCRIBE_WORDING

    shown = (await client.get("/api/site/")).json()["subscribe_consent_wording"]
    answer = await client.post(
        "/api/party/subscribe/", json={"contact": "0712345678", "consent_given": True}
    )
    recorded = await session.scalar(select(Subscriber.consent_wording))

    assert shown == recorded == CAMPAIGN_SUBSCRIBE_WORDING
    assert "party" not in (shown + answer.json()["message"]).lower()
