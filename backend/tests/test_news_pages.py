"""Event counties, and the About page's documents, values, organs and counts."""

import httpx

from tests.conftest import World

EVENT = {"kind": "event", "event_date": "2099-01-10", "published": True}


async def test_the_county_filter_narrows_events(
    client: httpx.AsyncClient, world: World, admin_headers: dict
) -> None:
    county = str(world.county.id)
    for title, county_id in (("Nairobi town hall", county), ("National rally", None)):
        body = {**EVENT, "title": title, "county_id": county_id}
        assert (
            await client.post("/api/admin/party/posts/", headers=admin_headers, json=body)
        ).status_code == 201

    every = (await client.get("/api/party/posts/?kind=event")).json()
    local = (await client.get(f"/api/party/posts/?kind=event&county={county}")).json()

    assert {e["title"] for e in every} == {"Nairobi town hall", "National rally"}
    assert [(e["title"], e["county"]["name"]) for e in local] == [
        ("Nairobi town hall", "Nairobi City")
    ]


async def test_the_about_page_lists_only_published_content(
    client: httpx.AsyncClient, admin_headers: dict
) -> None:
    for title, published in (("Constitution", True), ("Draft rules", False)):
        body = {"title": title, "url": "https://example.com/doc.pdf", "published": published}
        assert (
            await client.post("/api/admin/party/documents/", headers=admin_headers, json=body)
        ).status_code == 201
    video = {"title": "Rally", "url": "https://youtu.be/abc", "duration": "4:15"}
    for published in (True, False):
        body = {**video, "published": published}
        assert (
            await client.post("/api/admin/party/videos/", headers=admin_headers, json=body)
        ).status_code == 201
    for path in ("values", "organs"):
        for title, published in (("Shown", True), ("Hidden", False)):
            body = {"title": title, "text": "Why.", "published": published}
            assert (
                await client.post(f"/api/admin/party/{path}/", headers=admin_headers, json=body)
            ).status_code == 201

    documents = (await client.get("/api/party/documents/")).json()
    values = (await client.get("/api/party/values/")).json()
    organs = (await client.get("/api/party/organs/")).json()

    assert [d["title"] for d in documents] == ["Constitution"]
    assert [(v["title"], v["text"]) for v in values] == [("Shown", "Why.")]
    assert [o["title"] for o in organs] == ["Shown"]
    videos = (await client.get("/api/party/videos/")).json()
    assert [(v["title"], v["duration"]) for v in videos] == [("Rally", "4:15")]
