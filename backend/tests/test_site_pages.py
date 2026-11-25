"""Public pages carry their own title and link preview in the HTML, before any script runs."""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import World
from tests.factories import site_settings


async def test_a_shared_news_link_previews_its_own_title_text_and_photo(
    session: AsyncSession, client: httpx.AsyncClient, world: World
) -> None:
    session.add(site_settings(name="Amina for Ruai", slogan="Ruai first & always"))
    await session.commit()
    body = {
        "kind": "news",
        "title": 'Water for "Mihang\'o"',
        "body": "<p>Boreholes open <strong>next week</strong> in every village of the ward.</p>",
        "image_url": "https://images.example.com/x.jpg",
        "published": True,
    }
    await client.post("/api/workspace/site/posts/", headers=world.headers("manager"), json=body)

    home = (await client.get("/")).text
    story = await client.get("/news/water-for-mihang-o")
    missing = (await client.get("/news/no-such-story")).text

    assert "<title>Amina for Ruai</title>" in home
    assert 'content="Ruai first &amp; always"' in home
    assert story.status_code == 200
    assert "<title>Water for &quot;Mihang&#x27;o&quot; | Amina for Ruai</title>" in story.text
    assert 'content="Boreholes open next week in every village of the ward."' in story.text
    assert 'property="og:image" content="https://images.example.com/x.jpg"' in story.text
    assert "<title>Amina for Ruai</title>" in missing


async def test_the_site_icon_is_the_logo_tile_in_the_site_colours(
    session: AsyncSession, client: httpx.AsyncClient
) -> None:
    session.add(site_settings(name="Amina for Ruai", primary_colour="#123456"))
    await session.commit()

    icon = await client.get("/favicon.svg")

    assert icon.headers["content-type"] == "image/svg+xml"
    assert 'fill="#123456"' in icon.text and ">AF</text>" in icon.text
