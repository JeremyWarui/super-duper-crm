"""The reference-geography reads, and what each role is allowed to see."""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import UserRole, Ward
from tests.factories import (
    auth,
    make_campaign,
    make_geography,
    make_mobilizer_user,
    make_user,
    sign_in,
)

ENDPOINTS = ["/api/counties/", "/api/constituencies/", "/api/wards/", "/api/centres/"]


async def _manager_token(client: httpx.AsyncClient, session: AsyncSession) -> str:
    await make_user(session, username="amina", role=UserRole.MANAGER)
    return await sign_in(client, "amina")


async def test_every_geography_read_needs_a_token(client: httpx.AsyncClient) -> None:
    for path in ENDPOINTS:
        response = await client.get(path)
        assert response.status_code == 401, path


async def test_wards_filter_by_constituency(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _, constituency, ward, _ = await make_geography(session)
    token = await _manager_token(client, session)

    body = (
        await client.get(f"/api/wards/?constituency={constituency.id}", headers=auth(token))
    ).json()

    assert body[0]["id"] == str(ward.id)
    assert body[0]["constituency"] == str(constituency.id)
    assert body[0]["constituency_name"] == "Westlands"
    assert body[0]["registered_voters"] == 10_000


async def test_a_mobilizer_sees_only_their_own_ward(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _, constituency, ward, _ = await make_geography(session)
    elsewhere = Ward(constituency=constituency, name="Highridge", code="1371")
    session.add(elsewhere)
    await session.commit()
    campaign = await make_campaign(session, ward)
    await make_mobilizer_user(session, campaign, ward)
    token = await sign_in(client, "juma")

    body = (await client.get("/api/wards/", headers=auth(token))).json()

    assert [w["name"] for w in body] == ["Parklands"]
