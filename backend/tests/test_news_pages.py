"""Post text, and the published documents and videos."""

import httpx

from tests.conftest import World


async def test_only_published_documents_and_videos_are_listed(
    client: httpx.AsyncClient, world: World
) -> None:
    editor = world.headers("manager")
    for title, published in (("Constitution", True), ("Draft rules", False)):
        body = {"title": title, "url": "https://example.com/doc.pdf", "published": published}
        assert (
            await client.post("/api/workspace/site/documents/", headers=editor, json=body)
        ).status_code == 201
    video = {"title": "Rally", "url": "https://youtu.be/abc", "duration": "4:15"}
    for published in (True, False):
        body = {**video, "published": published}
        assert (
            await client.post("/api/workspace/site/videos/", headers=editor, json=body)
        ).status_code == 201

    documents = (await client.get("/api/website/documents/")).json()

    assert [d["title"] for d in documents] == ["Constitution"]
    videos = (await client.get("/api/website/videos/")).json()
    assert [(v["title"], v["duration"]) for v in videos] == [("Rally", "4:15")]


async def test_post_text_is_kept_as_cleaned_html_with_a_plain_excerpt(
    client: httpx.AsyncClient, world: World
) -> None:
    editor = world.headers("manager")
    written = (
        '<h2>Agreed</h2><p onclick="x()">Fees <strong>fall</strong> &amp; rise.</p>'
        '<script>alert(1)</script><a href="javascript:alert(1)">bad</a>'
        '<a href="/\\evil.com">far</a>'
    )
    post = await client.post(
        "/api/workspace/site/posts/",
        headers=editor,
        json={"kind": "news", "title": "Congress", "body": written, "published": True},
    )
    [public] = (await client.get("/api/website/posts/?kind=news")).json()

    assert post.status_code == 201
    assert public["body"] == (
        "<h2>Agreed</h2><p>Fees <strong>fall</strong> &amp; rise.</p>"
        '<a rel="noopener noreferrer">bad</a><a rel="noopener noreferrer">far</a>'
    )
    assert public["excerpt"] == "Agreed Fees fall & rise. badfar"
