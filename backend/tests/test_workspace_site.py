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
