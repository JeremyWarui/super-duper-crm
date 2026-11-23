"""Carousel slides and agenda issues: the website editor writes them, the public sees published
ones."""

import httpx

from tests.conftest import World

SLIDE = {"headline": "Together we build", "button_label": "Join", "button_url": "/volunteer"}


async def test_the_public_sees_only_published_slides_and_issues_in_order(
    client: httpx.AsyncClient, world: World
) -> None:
    editor = world.headers("manager")
    for order, published in ((2, True), (1, True), (0, False)):
        body = {**SLIDE, "headline": f"Slide {order}", "sort_order": order, "published": published}
        assert (
            await client.post("/api/workspace/site/slides/", headers=editor, json=body)
        ).status_code == 201
    draft = await client.post("/api/workspace/site/issues/", headers=editor, json={"title": "Jobs"})
    refused = await client.post(
        "/api/workspace/site/issues/", headers=world.headers("mobilizer"), json={"title": "Jobs"}
    )

    slides = (await client.get("/api/website/slides/")).json()
    assert [s["headline"] for s in slides] == ["Slide 1", "Slide 2"]
    assert (await client.get("/api/website/issues/")).json() == []
    assert (await client.get(f"/api/website/issues/{draft.json()['id']}/")).status_code == 404
    assert refused.status_code == 403


async def test_the_carousel_holds_at_most_five_slides(
    client: httpx.AsyncClient, world: World
) -> None:
    editor = world.headers("manager")
    answers = [
        (await client.post("/api/workspace/site/slides/", headers=editor, json=SLIDE)).status_code
        for _ in range(6)
    ]

    assert answers == [201] * 5 + [400]


async def test_a_published_issue_carries_its_photo_for_the_homepage_card(
    client: httpx.AsyncClient, world: World
) -> None:
    editor = world.headers("manager")
    photo = "https://example.org/clinic.jpg"
    made = await client.post(
        "/api/workspace/site/issues/",
        headers=editor,
        json={"title": "Health for every family", "image_url": photo, "published": True},
    )

    assert made.status_code == 201
    assert [i["image_url"] for i in (await client.get("/api/website/issues/")).json()] == [photo]
