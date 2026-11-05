"""The Results page: published primary results, and demo results marked as such."""

from datetime import date

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.seed.site import seed_news, seed_site

pytestmark = pytest.mark.party_only


async def test_only_published_results_show_ordered_by_seat_and_votes(
    client: httpx.AsyncClient, admin_headers: dict
) -> None:
    for seat, area, name, votes, published in (
        ("mp", "Westlands", "Lucy Wairimu", 400, True),
        ("mp", "Westlands", "Brian Ochieng", 900, True),
        ("governor", "Nakuru County", "Mary Njeri", 1200, True),
        ("mp", "Westlands", "Hidden Draft", 5000, False),
    ):
        body = {"seat": seat, "area": area, "candidate": name, "votes": votes}
        body["published"] = published
        assert (
            await client.post("/api/admin/party/results/", headers=admin_headers, json=body)
        ).status_code == 201

    shown = (await client.get("/api/party/results/")).json()

    assert [(r["seat"], r["candidate"], r["demo"]) for r in shown] == [
        ("governor", "Mary Njeri", False),
        ("mp", "Brian Ochieng", False),
        ("mp", "Lucy Wairimu", False),
    ]


async def test_the_seed_marks_its_results_as_demo(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await seed_site(session, date(2026, 11, 1))
    await seed_news(session, date(2026, 11, 1))

    shown = (await client.get("/api/party/results/")).json()
    party = (await client.get("/api/party/")).json()

    assert shown and all(r["demo"] for r in shown)
    assert party["aspirant_steps"].startswith("Be a paid-up party member")
