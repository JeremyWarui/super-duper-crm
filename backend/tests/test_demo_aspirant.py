"""The demo install: one run sets up an empty database with every sign-in working."""

from datetime import date

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_today
from backend.main import app
from backend.models import Supporter
from backend.seed.demo_aspirant import build_aspirant
from backend.seed.demo_laikipia import LAIKIPIA
from backend.seed.reference import import_geography
from backend.services.errors import Refused
from tests.factories import auth, fresh_password


async def test_the_aspirant_demo_signs_everyone_in_with_a_published_page(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await import_geography(session)
    password = fresh_password()

    # The CLI's sessions never autoflush.
    async with AsyncSession(session.bind, expire_on_commit=False, autoflush=False) as cli:
        sign_ins = await build_aspirant(cli, password=password, today=date(2026, 11, 1))

    tokens = {}
    for s in sign_ins:
        login = {"email": s.email, "password": password}
        answer = await client.post("/api/auth/login/", json=login)
        assert answer.status_code == 200, (s.email, answer.text)
        tokens[s.email.split("@")[0]] = answer.json()["token"]
    assert set(tokens) == {"admin", "candidate", "manager", "mobilizer"}

    page = (await client.get("/api/site/candidate/")).json()
    agenda = (await client.get("/api/website/issues/")).json()
    slides = (await client.get("/api/website/slides/")).json()
    assert page["name"] == "David Otieno"
    shared = [(i["title"], i["image_url"]) for i in agenda[:3]]
    assert [(p["title"], p["image_url"]) for p in page["priorities"]] == shared
    assert all(i["image_url"].startswith("https://") for i in agenda)
    assert (len(agenda), len(slides)) == (6, 3)
    site = (await client.get("/api/site/")).json()
    assert site["slogan"] and site["description"] and site["mpesa_paybill"]
    news = (await client.get("/api/website/posts/", params={"kind": "news"})).json()
    app.dependency_overrides[get_today] = lambda: date(2026, 11, 1)
    try:
        events = (await client.get("/api/website/events/")).json()
    finally:
        app.dependency_overrides.pop(get_today, None)
    documents = (await client.get("/api/website/documents/")).json()
    videos = (await client.get("/api/website/videos/")).json()
    assert (len(news), len(events), len(documents), len(videos)) == (6, 4, 4, 3)
    assert {p["label"] for p in news} == {"news", "statement", "opinion"}
    assert all(p["image_url"].startswith("https://") for p in news + events)
    campaign_id = (await client.get("/api/campaigns/", headers=auth(tokens["manager"]))).json()[0][
        "id"
    ]
    mobilizers = (
        await client.get(
            f"/api/mobilizers/?campaign={campaign_id}", headers=auth(tokens["manager"])
        )
    ).json()
    login = (await client.get("/api/auth/me/", headers=auth(tokens["mobilizer"]))).json()
    names = {m["full_name"] for m in mobilizers}
    assert login["full_name"] in names
    assert all(m["phone"] and not m["full_name"].startswith("Organiser") for m in mobilizers)
    for who in ("candidate", "manager", "mobilizer"):
        campaigns = await client.get("/api/campaigns/", headers=auth(tokens[who]))
        assert [c["title"] for c in campaigns.json()] == ["David Otieno for Kasarani"]


async def test_the_aspirant_demo_refuses_a_database_already_set_up(
    session: AsyncSession,
) -> None:
    await import_geography(session)
    await build_aspirant(session, password=fresh_password(), today=date(2026, 11, 1))

    with pytest.raises(Refused):
        await build_aspirant(session, password=fresh_password(), today=date(2026, 11, 1))


async def test_the_laikipia_demo_is_a_governor_campaign_with_five_logins(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await import_geography(session)
    password = fresh_password()

    async with AsyncSession(session.bind, expire_on_commit=False, autoflush=False) as cli:
        sign_ins = await build_aspirant(
            cli, password=password, today=date(2026, 11, 1), demo=LAIKIPIA
        )

    tokens = {}
    for s in sign_ins:
        answer = await client.post(
            "/api/auth/login/", json={"email": s.email, "password": password}
        )
        assert answer.status_code == 200, (s.email, answer.text)
        tokens[s.email.split("@")[0]] = answer.json()["token"]
    me = {
        who: (await client.get("/api/auth/me/", headers=auth(token))).json()["full_name"]
        for who, token in tokens.items()
    }
    (campaign,) = (await client.get("/api/campaigns/", headers=auth(tokens["manager"]))).json()
    mobilizers = (
        await client.get(
            f"/api/mobilizers/?campaign={campaign['id']}", headers=auth(tokens["manager"])
        )
    ).json()

    assert set(tokens) == {"admin", "candidate", "manager", "coordinator", "mobilizer"}
    assert (me["candidate"], me["manager"], me["mobilizer"]) == ("Aspirant", "Jeremy", "Dennis")
    assert (campaign["title"], campaign["office_level"]) == ("Aspirant for Laikipia", "county")
    assert [m["ward_name"] for m in mobilizers if m["full_name"] == "Dennis"] == ["Nanyuki"]
    assert sign_ins[-1].sees == "Nanyuki only"
    assert await session.scalar(select(func.count()).select_from(Supporter)) == 20
