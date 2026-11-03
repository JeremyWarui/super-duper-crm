"""Carousel slides and agenda issues: the superuser writes them, the public sees published ones."""

import httpx

from tests.conftest import World

SLIDE = {"headline": "Together we build", "button_label": "Join", "button_url": "/join-party"}


async def test_the_public_sees_only_published_slides_and_issues_in_order(
    client: httpx.AsyncClient, world: World, admin_headers: dict
) -> None:
    for order, published in ((2, True), (1, True), (0, False)):
        body = {**SLIDE, "headline": f"Slide {order}", "sort_order": order, "published": published}
        assert (
            await client.post("/api/admin/party/slides/", headers=admin_headers, json=body)
        ).status_code == 201
    draft = await client.post(
        "/api/admin/party/issues/", headers=admin_headers, json={"title": "Jobs"}
    )
    refused = await client.post(
        "/api/admin/party/issues/", headers=world.headers("manager"), json={"title": "Jobs"}
    )

    slides = (await client.get("/api/party/slides/")).json()
    assert [s["headline"] for s in slides] == ["Slide 1", "Slide 2"]
    assert (await client.get("/api/party/issues/")).json() == []
    assert (await client.get(f"/api/party/issues/{draft.json()['id']}/")).status_code == 404
    assert refused.status_code == 403


async def test_the_carousel_holds_at_most_five_slides(
    client: httpx.AsyncClient, admin_headers: dict
) -> None:
    answers = [
        (
            await client.post("/api/admin/party/slides/", headers=admin_headers, json=SLIDE)
        ).status_code
        for _ in range(6)
    ]

    assert answers == [201] * 5 + [400]
