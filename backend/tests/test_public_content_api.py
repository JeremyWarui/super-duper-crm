"""Leaders and posts: the public sees only what is published; only the superuser edits."""

import uuid
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AuditEvent, OrganisationType, PartyRoleName
from tests.conftest import World
from tests.factories import TEST_TODAY, auth, make_officer, sign_in

LEADERS = "/api/admin/party/leaders/"
POSTS = "/api/admin/party/posts/"


def _event(day, **fields) -> dict:
    return {"kind": "event", "title": "Rally", "event_date": day.isoformat(), **fields}


async def test_drafts_never_reach_the_public(
    client: httpx.AsyncClient, admin_headers: dict, organisation_type: OrganisationType
) -> None:
    await client.post(LEADERS, headers=admin_headers, json={"name": "A", "position": "Chair"})
    await client.post(
        LEADERS,
        headers=admin_headers,
        json={"name": "B", "position": "Leader", "published": True},
    )
    draft = (
        await client.post(POSTS, headers=admin_headers, json={"kind": "news", "title": "Draft"})
    ).json()
    await client.post(
        POSTS, headers=admin_headers, json={"kind": "news", "title": "Out", "published": True}
    )
    for title, published in (("Draft rally", False), ("Rally", True)):
        await client.post(
            POSTS,
            headers=admin_headers,
            json={
                "kind": "event",
                "title": title,
                "event_date": "2026-11-20",
                "published": published,
            },
        )

    leaders = await client.get("/api/party/leaders/")
    news = (await client.get("/api/party/posts/", params={"kind": "news"})).json()
    events = (await client.get("/api/party/posts/", params={"kind": "event"})).json()
    by_id = await client.get(f"/api/party/posts/{draft['id']}/")

    if organisation_type is OrganisationType.PARTY:
        assert [leader["name"] for leader in leaders.json()] == ["B"]
    else:
        assert leaders.status_code == 404
    assert [post["title"] for post in news] == ["Out"]
    assert [post["title"] for post in events] == ["Rally"]
    assert by_id.status_code == 404


async def test_the_first_publish_dates_a_post_and_the_audit_holds_no_text(
    client: httpx.AsyncClient, session: AsyncSession, admin_headers: dict
) -> None:
    from backend.api.deps import get_today
    from backend.main import app

    post = (
        await client.post(POSTS, headers=admin_headers, json={"kind": "news", "title": "Secret"})
    ).json()
    url = f"{POSTS}{post['id']}/"
    first = (await client.patch(url, headers=admin_headers, json={"published": True})).json()
    await client.patch(url, headers=admin_headers, json={"published": False})
    app.dependency_overrides[get_today] = lambda: TEST_TODAY + timedelta(days=5)
    again = (await client.patch(url, headers=admin_headers, json={"published": True})).json()

    details = list(
        await session.scalars(
            select(AuditEvent.detail).where(AuditEvent.subject_id == uuid.UUID(post["id"]))
        )
    )
    assert first["published_on"] == again["published_on"] == TEST_TODAY.isoformat()
    assert len(details) == 4
    assert "Secret" not in str(details)


async def test_the_public_events_list_starts_today(
    client: httpx.AsyncClient, admin_headers: dict
) -> None:
    for day in (TEST_TODAY - timedelta(days=1), TEST_TODAY, TEST_TODAY + timedelta(days=3)):
        await client.post(
            POSTS, headers=admin_headers, json=_event(day, title=day.isoformat(), published=True)
        )

    events = (await client.get("/api/party/posts/", params={"kind": "event"})).json()

    assert [event["event_date"] for event in events] == [
        TEST_TODAY.isoformat(),
        (TEST_TODAY + timedelta(days=3)).isoformat(),
    ]


@pytest.mark.parametrize("url", ["http://example.com/a.jpg", "javascript:alert(1)"])
async def test_an_image_must_be_an_https_address(
    client: httpx.AsyncClient, admin_headers: dict, url: str, organisation_type: OrganisationType
) -> None:
    leader = await client.post(
        LEADERS, headers=admin_headers, json={"name": "A", "position": "Chair", "photo_url": url}
    )
    post = await client.post(
        POSTS, headers=admin_headers, json={"kind": "news", "title": "T", "image_url": url}
    )

    leaders_exist = organisation_type is OrganisationType.PARTY
    assert (leader.status_code, post.status_code) == (400 if leaders_exist else 404, 400)


EDITING = [
    ("GET", LEADERS),
    ("POST", LEADERS),
    ("PATCH", f"{LEADERS}{uuid.uuid4()}/"),
    ("DELETE", f"{LEADERS}{uuid.uuid4()}/"),
    ("GET", POSTS),
    ("POST", POSTS),
    ("PATCH", f"{POSTS}{uuid.uuid4()}/"),
    ("DELETE", f"{POSTS}{uuid.uuid4()}/"),
]


@pytest.mark.parametrize("role", ["candidate", "manager", "mobilizer", "officer"])
async def test_only_the_superuser_edits_content(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    role: str,
    organisation_type: OrganisationType,
) -> None:
    if role == "officer":
        await make_officer(session, world.ward, *PartyRoleName, username="ofisa")
        headers = auth(await sign_in(client, "ofisa"))
    else:
        headers = world.headers(role)

    answers = {
        (method, url): (await client.request(method, url, headers=headers, json={})).status_code
        for method, url in EDITING
    }

    leaders = 403 if organisation_type is OrganisationType.PARTY else 404
    assert answers == {
        (method, url): leaders if url.startswith(LEADERS) else 403 for method, url in EDITING
    }
