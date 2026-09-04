"""The reference-geography reads, and what each role is allowed to see."""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Constituency, County, RegistrationCentre, UserRole, Ward
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


async def test_a_county_carries_its_register_and_its_2022_turnout(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    county, *_ = await make_geography(session)
    token = await _manager_token(client, session)

    body = (await client.get("/api/counties/", headers=auth(token))).json()

    assert len(body) == 1
    assert body[0] == {
        "id": str(county.id),
        "name": "Nairobi",
        "code": "047",
        "registered_voters": 2_400_000,
        "turnout_2022_pct": None,
    }


async def test_one_county_can_be_fetched_by_id(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    county, *_ = await make_geography(session)
    token = await _manager_token(client, session)

    response = await client.get(f"/api/counties/{county.id}/", headers=auth(token))

    assert response.status_code == 200
    assert response.json()["name"] == "Nairobi"


async def test_an_unknown_county_is_404_not_500(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await make_geography(session)
    token = await _manager_token(client, session)

    response = await client.get(
        "/api/counties/00000000-0000-0000-0000-000000000009/", headers=auth(token)
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "No such county."


async def test_a_constituency_names_its_county_without_a_second_request(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    county, constituency, *_ = await make_geography(session)
    token = await _manager_token(client, session)

    body = (await client.get("/api/constituencies/", headers=auth(token))).json()

    assert body[0]["county"] == str(county.id)
    assert body[0]["county_name"] == "Nairobi"
    assert body[0]["name"] == "Westlands"


async def test_constituencies_filter_by_county(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    county, _, _, _ = await make_geography(session)
    other = County(name="Kisumu", code="042")
    session.add(Constituency(county=other, name="Kisumu Central", code="241"))
    await session.commit()
    token = await _manager_token(client, session)

    mine = (
        await client.get(f"/api/constituencies/?county={county.id}", headers=auth(token))
    ).json()
    theirs = (
        await client.get(f"/api/constituencies/?county={other.id}", headers=auth(token))
    ).json()

    assert [c["name"] for c in mine] == ["Westlands"]
    assert [c["name"] for c in theirs] == ["Kisumu Central"]


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


async def test_centres_filter_by_ward(client: httpx.AsyncClient, session: AsyncSession) -> None:
    _, _, ward, centre = await make_geography(session)
    token = await _manager_token(client, session)

    body = (await client.get(f"/api/centres/?ward={ward.id}", headers=auth(token))).json()

    assert body[0]["id"] == str(centre.id)
    assert body[0]["ward_name"] == "Parklands"
    assert body[0]["registered_voters"] == 2_000


async def test_a_candidate_may_read_the_geography(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await make_geography(session)
    await make_user(session, username="jane", role=UserRole.CANDIDATE)
    token = await sign_in(client, "jane")

    for path in ENDPOINTS:
        assert (await client.get(path, headers=auth(token))).status_code == 200, path


# ---------------------------------------------------- what a mobilizer may see


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


async def test_a_mobilizer_sees_only_the_centres_in_their_ward(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _, constituency, ward, centre = await make_geography(session)
    elsewhere = Ward(constituency=constituency, name="Highridge", code="1371")
    session.add(RegistrationCentre(ward=elsewhere, name="Highridge Primary", code="002"))
    await session.commit()
    campaign = await make_campaign(session, ward)
    await make_mobilizer_user(session, campaign, ward)
    token = await sign_in(client, "juma")

    body = (await client.get("/api/centres/", headers=auth(token))).json()

    assert [c["id"] for c in body] == [str(centre.id)]


async def test_asking_for_another_ward_still_returns_only_their_own(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _, constituency, ward, _ = await make_geography(session)
    elsewhere = Ward(constituency=constituency, name="Highridge", code="1371")
    session.add(elsewhere)
    await session.commit()
    campaign = await make_campaign(session, ward)
    await make_mobilizer_user(session, campaign, ward)
    token = await sign_in(client, "juma")

    body = (
        await client.get(f"/api/wards/?constituency={constituency.id}", headers=auth(token))
    ).json()

    assert [w["name"] for w in body] == ["Parklands"]


async def test_a_mobilizer_with_no_profile_sees_no_wards(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await make_geography(session)
    await make_user(session, username="stray", role=UserRole.MOBILIZER)
    token = await sign_in(client, "stray")

    assert (await client.get("/api/wards/", headers=auth(token))).json() == []
    assert (await client.get("/api/centres/", headers=auth(token))).json() == []


async def test_wards_filter_by_county(client: httpx.AsyncClient, session: AsyncSession) -> None:
    county, constituency, ward, _ = await make_geography(session)
    second = Constituency(county=county, name="Dagoretti North", code="275")
    session.add(Ward(constituency=second, name="Kilimani", code="1372", registered_voters=20_000))
    elsewhere = County(name="Kisumu", code="042")
    other_constituency = Constituency(county=elsewhere, name="Kisumu Central", code="241")
    session.add(Ward(constituency=other_constituency, name="Railways", code="0001"))
    await session.commit()
    token = await _manager_token(client, session)

    body = (await client.get(f"/api/wards/?county={county.id}", headers=auth(token))).json()

    assert sorted(w["name"] for w in body) == ["Kilimani", "Parklands"]
    assert str(ward.id) in {w["id"] for w in body}


async def test_a_mobilizer_asking_for_a_whole_county_still_gets_one_ward(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    county, constituency, ward, _ = await make_geography(session)
    session.add(Ward(constituency=constituency, name="Highridge", code="1371"))
    await session.commit()
    campaign = await make_campaign(session, ward)
    await make_mobilizer_user(session, campaign, ward)
    token = await sign_in(client, "juma")

    body = (await client.get(f"/api/wards/?county={county.id}", headers=auth(token))).json()

    assert [w["name"] for w in body] == ["Parklands"]
