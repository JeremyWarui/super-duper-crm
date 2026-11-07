"""First-run setup: the 503 guard, the one-time token, and the installation it makes."""

import re
import secrets
from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_organisation_type
from backend.main import app
from backend.models import AuditEvent, Campaign, CandidateProfile, SiteSettings, User, WorkspaceKind
from backend.services import setup, site
from tests.conftest import app_client
from tests.factories import fresh_password, make_geography

pytestmark = pytest.mark.party_only


@pytest.fixture
async def bare(session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    """The app reading its real state: no site settings until setup makes them."""
    site._organisation_type = None
    try:
        async with app_client(session) as client:
            del app.dependency_overrides[get_organisation_type]
            yield client
    finally:
        site._organisation_type = None


def _request(token: str, ward_id, **changes) -> dict:
    body = {
        "token": token,
        "organisation_type": "aspirant",
        "site": {
            "name": "Jane for Parklands",
            "primary_colour": "#0B5D3B",
            "secondary_colour": "#F2B705",
        },
        "superuser": {
            "username": "owner",
            "email": "owner@example.com",
            "password": fresh_password(),
        },
        "aspirant": {
            "title": "Jane for Parklands",
            "seat": "mca",
            "ward": str(ward_id),
            "candidate": {"username": "jane", "email": "jane@example.com", "first_name": "Jane"},
        },
    }
    return {**body, **changes}


async def test_every_route_but_setup_and_health_answers_503_before_setup(
    bare: httpx.AsyncClient,
) -> None:
    paths = {
        (method, re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", route.path))
        for route in app.routes
        if getattr(route, "path", "").startswith("/api/")
        for method in getattr(route, "methods", ()) - {"HEAD", "OPTIONS"}
    }
    answers = {(m, p): (await bare.request(m, p, json={})).status_code for m, p in paths}

    open_paths = {(m, p) for m, p in paths if p.startswith("/api/setup/")}
    assert {k: v for k, v in answers.items() if k not in open_paths and v != 503} == {}
    assert (await bare.get("/api/setup/")).json() == {"set_up": False}
    assert (await bare.get("/health")).status_code == 200
    blocked = await bare.get("/api/site/")
    assert blocked.json()["code"] == "not_set_up"


async def test_a_wrong_or_replaced_token_is_refused(
    bare: httpx.AsyncClient, session: AsyncSession
) -> None:
    first = await setup.new_token(session)
    second = await setup.new_token(session)

    wrong = secrets.token_urlsafe(32)
    assert (await bare.post("/api/setup/check/", json={"token": wrong})).status_code == 403
    assert (await bare.post("/api/setup/check/", json={"token": first})).status_code == 403
    assert (await bare.post("/api/setup/check/", json={"token": second})).status_code == 204


async def test_the_aspirant_path_makes_one_standalone_workspace_and_the_candidate_login(
    bare: httpx.AsyncClient, session: AsyncSession
) -> None:
    *_, ward, _ = await make_geography(session)
    token = await setup.new_token(session)

    answer = await bare.post("/api/setup/", json=_request(token, ward.id))

    assert answer.status_code == 201, answer.text
    assert answer.json()["invites"] == ["email"]
    workspaces = (await session.scalars(select(Campaign))).all()
    assert [w.kind for w in workspaces] == [WorkspaceKind.STANDALONE]
    assert await session.scalar(select(func.count(CandidateProfile.id))) == 1
    jane = await session.scalar(select(User).where(User.username == "jane"))
    owner = await session.scalar(select(User).where(User.username == "owner"))
    assert (jane.role.value, owner.is_superuser) == ("candidate", True)
    assert (await session.get(SiteSettings, 1)).organisation_type.value == "aspirant"
    assert await session.scalar(select(AuditEvent.id).where(AuditEvent.action == "setup.completed"))
    assert (await bare.get("/api/site/")).status_code == 200


@pytest.mark.parametrize("kind", ["party", "aspirant"])
async def test_staff_need_2_step_by_default_in_a_party_copy_only(
    bare: httpx.AsyncClient, session: AsyncSession, kind: str
) -> None:
    *_, ward, _ = await make_geography(session)
    token = await setup.new_token(session)
    changes = {"organisation_type": "party", "aspirant": None} if kind == "party" else {}

    answer = await bare.post("/api/setup/", json=_request(token, ward.id, **changes))

    assert answer.status_code == 201, answer.text
    required = (await session.get(SiteSettings, 1)).staff_two_step_required
    assert required is (kind == "party")


async def test_setup_cannot_run_twice_and_its_token_is_spent(
    bare: httpx.AsyncClient, session: AsyncSession
) -> None:
    *_, ward, _ = await make_geography(session)
    token = await setup.new_token(session)
    assert (await bare.post("/api/setup/", json=_request(token, ward.id))).status_code == 201

    again = await bare.post("/api/setup/", json=_request(token, ward.id))

    assert again.status_code == 400
    assert "already set up" in again.json()["detail"]
    with pytest.raises(Exception, match="already set up"):
        await setup.new_token(session)


async def test_a_refused_setup_writes_nothing_and_keeps_the_token(
    bare: httpx.AsyncClient, session: AsyncSession
) -> None:
    *_, ward, _ = await make_geography(session)
    token = await setup.new_token(session)
    clash = _request(token, ward.id)
    clash["aspirant"]["candidate"]["username"] = "owner"

    answer = await bare.post("/api/setup/", json=clash)

    assert answer.status_code == 400
    assert await session.get(SiteSettings, 1) is None
    assert await session.scalar(select(func.count(User.id))) == 0
    assert (await bare.post("/api/setup/check/", json={"token": token})).status_code == 204
