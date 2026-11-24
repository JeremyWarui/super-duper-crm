"""Posts: the public sees only what is published, and what the editor writes is checked."""

import uuid
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AuditEvent
from tests.conftest import World
from tests.factories import TEST_TODAY

POSTS = "/api/workspace/site/posts/"


def _event(day, **fields) -> dict:
    return {"kind": "event", "title": "Rally", "event_date": day.isoformat(), **fields}


async def test_drafts_never_reach_the_public(client: httpx.AsyncClient, world: World) -> None:
    editor = world.headers("manager")
    draft = (
        await client.post(POSTS, headers=editor, json={"kind": "news", "title": "Draft"})
    ).json()
    await client.post(
        POSTS, headers=editor, json={"kind": "news", "title": "Out", "published": True}
    )

    news = (await client.get("/api/website/posts/", params={"kind": "news"})).json()
    by_id = await client.get(f"/api/website/posts/{draft['id']}/")

    assert [post["title"] for post in news] == ["Out"]
    assert by_id.status_code == 404


async def test_the_first_publish_dates_a_post_and_the_audit_holds_no_text(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    from backend.api.deps import get_today

    editor = world.headers("manager")
    from backend.main import app

    post = (
        await client.post(POSTS, headers=editor, json={"kind": "news", "title": "Secret"})
    ).json()
    url = f"{POSTS}{post['id']}/"
    first = (await client.patch(url, headers=editor, json={"published": True})).json()
    await client.patch(url, headers=editor, json={"published": False})
    app.dependency_overrides[get_today] = lambda: TEST_TODAY + timedelta(days=5)
    again = (await client.patch(url, headers=editor, json={"published": True})).json()

    details = list(
        await session.scalars(
            select(AuditEvent.detail).where(AuditEvent.subject_id == uuid.UUID(post["id"]))
        )
    )
    assert first["published_on"] == again["published_on"] == TEST_TODAY.isoformat()
    assert len(details) == 4
    assert "Secret" not in str(details)


async def test_an_event_is_not_a_post(client: httpx.AsyncClient, world: World) -> None:
    """Events are the campaign's own, put on the website from Events; the editor makes news."""
    refused = await client.post(
        POSTS, headers=world.headers("manager"), json=_event(TEST_TODAY, published=True)
    )
    listed = (await client.get("/api/website/posts/", params={"kind": "event"})).json()

    assert refused.status_code == 400
    assert listed == []


@pytest.mark.parametrize("url", ["http://example.com/a.jpg", "javascript:alert(1)"])
async def test_an_image_must_be_an_https_address(
    client: httpx.AsyncClient, world: World, url: str
) -> None:
    post = await client.post(
        POSTS,
        headers=world.headers("manager"),
        json={"kind": "news", "title": "T", "image_url": url},
    )

    assert post.status_code == 400


async def test_a_statement_takes_an_uploaded_pdf(client: httpx.AsyncClient, world: World) -> None:
    editor = world.headers("manager")
    upload = f"/api/files/{uuid.uuid4()}/"
    post = await client.post(
        POSTS,
        headers=editor,
        json={"kind": "news", "label": "statement", "title": "T", "pdf_url": upload},
    )
    assert post.status_code == 201, post.text
    assert post.json()["pdf_url"] == upload
