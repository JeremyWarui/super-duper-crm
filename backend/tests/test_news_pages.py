"""Event counties and party documents on the public news, events and About pages."""

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


async def test_the_about_page_lists_only_published_documents(
    client: httpx.AsyncClient, admin_headers: dict
) -> None:
    for title, published in (("Constitution", True), ("Draft rules", False)):
        body = {"title": title, "url": "https://example.com/doc.pdf", "published": published}
        assert (
            await client.post("/api/admin/party/documents/", headers=admin_headers, json=body)
        ).status_code == 201

    documents = (await client.get("/api/party/documents/")).json()

    assert [d["title"] for d in documents] == ["Constitution"]
