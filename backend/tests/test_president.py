"""A Presidential campaign: targets over the whole country, coordinators confined to a county."""

from decimal import Decimal

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Constituency, County, OfficeLevel, Seat, UserRole, Ward
from backend.services.accounts import add_member
from backend.services.campaigns import build_campaign
from tests.factories import make_user, sign_in


async def _two_counties(session: AsyncSession) -> tuple[Ward, Ward, Ward]:
    """Nairobi at 60% turnout with two wards, Mombasa at 50% with one."""
    nairobi = County(name="Nairobi City", code="047", turnout_2022_pct=Decimal("60.00"))
    mombasa = County(name="Mombasa", code="001", turnout_2022_pct=Decimal("50.00"))
    roysambu = Constituency(county=nairobi, name="Roysambu", code="279")
    mvita = Constituency(county=mombasa, name="Mvita", code="006")
    wards = (
        Ward(constituency=roysambu, name="Zimmerman", code="1393", registered_voters=30_000),
        Ward(constituency=roysambu, name="Githurai", code="1391", registered_voters=20_000),
        Ward(constituency=mvita, name="Majengo", code="0030", registered_voters=10_000),
    )
    session.add_all(wards)
    await session.commit()
    return wards


async def test_a_presidential_campaign_targets_every_ward_in_every_county(
    session: AsyncSession, client: httpx.AsyncClient
) -> None:
    await _two_counties(session)
    campaign, summary = await build_campaign(session, title="Jane for Kenya", seat=Seat.PRESIDENT)
    candidate = await make_user(session, username="jane", role=UserRole.CANDIDATE)
    await add_member(session, campaign.id, candidate)
    await session.commit()

    strategy = await client.get(
        f"/api/strategy/?campaign={campaign.id}",
        headers={"Authorization": f"Token {await sign_in(client, 'jane')}"},
    )

    body = strategy.json()
    assert campaign.office_level is OfficeLevel.NATIONAL
    assert (campaign.county_id, campaign.constituency_id, campaign.ward_id) == (None, None, None)
    # 30,000 and 20,000 at 60% need 9,001 and 6,001; 10,000 at 50% needs 2,501.
    assert (summary.units, summary.total_registered, summary.win_number) == (3, 60_000, 17_503)
    assert body["win_number"] == 17_503
    assert body["units"] == []
    assert body["group_level"] == "county"
    assert [(g["name"], g["units"], g["needed"]) for g in body["groups"]] == [
        ("Mombasa", 1, 2_501),
        ("Nairobi City", 2, 15_002),
    ]


async def test_a_county_coordinator_on_a_presidential_campaign_stays_in_their_county(
    session: AsyncSession, client: httpx.AsyncClient
) -> None:
    zimmerman, githurai, majengo = await _two_counties(session)
    campaign, _ = await build_campaign(session, title="Jane for Kenya", seat=Seat.PRESIDENT)
    candidate = await make_user(session, username="jane", role=UserRole.CANDIDATE)
    coordinator = await make_user(session, username="otieno", role=UserRole.COORDINATOR)
    for user in (candidate, coordinator):
        await add_member(session, campaign.id, user)
    await session.commit()
    lead = {"Authorization": f"Token {await sign_in(client, 'jane')}"}
    nairobi = zimmerman.constituency.county_id

    given = await client.put(
        f"/api/campaigns/{campaign.id}/team/{coordinator.id}/area/",
        headers=lead,
        json={"counties": [str(nairobi)]},
    )
    head = {"Authorization": f"Token {await sign_in(client, 'otieno')}"}
    targets = (await client.get(f"/api/targets/?campaign={campaign.id}", headers=head)).json()
    in_mombasa = await client.post(
        "/api/events/",
        headers=head,
        json={"campaign": str(campaign.id), "ward": str(majengo.id), "title": "Rally"},
    )
    in_nairobi = await client.post(
        "/api/events/",
        headers=head,
        json={"campaign": str(campaign.id), "ward": str(githurai.id), "title": "Rally"},
    )

    assert given.json()["counties"] == [str(nairobi)]
    assert sorted(t["ward_name"] for t in targets) == ["Githurai", "Zimmerman"]
    assert in_mombasa.status_code == 403
    assert in_nairobi.status_code == 201
