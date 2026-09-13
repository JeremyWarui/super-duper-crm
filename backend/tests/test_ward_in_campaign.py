"""A ward or centre named in a body has to lie inside the campaign's own seat.

Ids arrive from the client. A row filed under a ward the campaign does not
contest has no target, so no strategy read counts it and the targeting table
never shows it.
"""

import uuid
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Campaign,
    CampaignMember,
    Constituency,
    County,
    Event,
    Mobilizer,
    OfficeLevel,
    Supporter,
    Target,
    User,
    UserRole,
    Ward,
)
from backend.services.targets import ward_in_area
from tests.conftest import World
from tests.factories import auth, make_user, sign_in

OUTSIDE = "That ward is not one this campaign works."


async def _elsewhere(session: AsyncSession, world: World) -> Ward:
    """A ward in another constituency of the same county, which no target covers."""
    other = Constituency(county_id=world.county.id, name="Kasarani", code="281")
    ward = Ward(constituency=other, name="Mwiki", code="1450", registered_voters=21_000)
    session.add_all([other, ward])
    await session.commit()
    return ward


async def _admin(session: AsyncSession, client: httpx.AsyncClient) -> dict[str, str]:
    root = await make_user(session, username="root", role=UserRole.MANAGER)
    root.is_superuser = True
    await session.commit()
    return auth(await sign_in(client, "root"))


# ------------------------------------------------------------ the rule itself


async def test_ward_in_area_holds_a_ward_race_to_its_own_ward(
    session: AsyncSession, world: World
) -> None:
    race = Campaign(office_level=OfficeLevel.WARD, ward_id=world.ward.id)

    assert await ward_in_area(session, race, world.ward.id)
    assert not await ward_in_area(session, race, world.other_ward.id)


async def test_ward_in_area_holds_a_constituency_race_to_its_constituency(
    session: AsyncSession, world: World
) -> None:
    outside = await _elsewhere(session, world)

    assert await ward_in_area(session, world.campaign, world.ward.id)
    assert await ward_in_area(session, world.campaign, world.other_ward.id)
    assert not await ward_in_area(session, world.campaign, outside.id)


async def test_ward_in_area_holds_a_county_race_to_its_county(
    session: AsyncSession, world: World
) -> None:
    far = County(name="Mombasa", code="001", turnout_2022_pct=Decimal("55.00"))
    coast = Constituency(county=far, name="Changamwe", code="001")
    port = Ward(constituency=coast, name="Port Reitz", code="0001", registered_voters=19_000)
    session.add_all([far, coast, port])
    await session.commit()
    race = Campaign(office_level=OfficeLevel.COUNTY, county_id=world.county.id)

    assert await ward_in_area(session, race, world.ward.id)
    assert not await ward_in_area(session, race, port.id)


async def test_ward_in_area_refuses_a_campaign_with_no_area_set(
    session: AsyncSession, world: World
) -> None:
    unset = Campaign(office_level=OfficeLevel.CONSTITUENCY, constituency_id=None)

    assert not await ward_in_area(session, unset, world.ward.id)


# ----------------------------------------------- every route that names a ward


async def test_a_mobilizer_cannot_be_put_on_a_ward_outside_the_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    outside = await _elsewhere(session, world)

    refused = await client.post(
        "/api/mobilizers/",
        headers=world.headers("manager"),
        json={
            "campaign": str(world.campaign.id),
            "ward": str(outside.id),
            "full_name": "Stray Boots",
        },
    )

    assert refused.status_code == 400
    assert refused.json()["detail"] == OUTSIDE
    assert (
        await session.scalar(select(Mobilizer).where(Mobilizer.full_name == "Stray Boots")) is None
    )


async def test_a_supporter_cannot_be_registered_in_a_ward_outside_the_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    outside = await _elsewhere(session, world)

    refused = await client.post(
        "/api/supporters/",
        headers=world.headers("manager"),
        json={
            "campaign": str(world.campaign.id),
            "ward": str(outside.id),
            "full_name": "Ghost Voter",
            "phone": "+254700111333",
            "support_level": "supporter",
            "consent_given": True,
        },
    )

    assert refused.status_code == 400
    assert refused.json()["detail"] == OUTSIDE
    assert (
        await session.scalar(select(Supporter).where(Supporter.full_name == "Ghost Voter")) is None
    )


async def test_an_event_cannot_be_scheduled_in_a_ward_outside_the_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    outside = await _elsewhere(session, world)

    refused = await client.post(
        "/api/events/",
        headers=world.headers("manager"),
        json={
            "campaign": str(world.campaign.id),
            "ward": str(outside.id),
            "title": "Rally nowhere",
            "venue": "Nowhere",
        },
    )

    assert refused.status_code == 400
    assert refused.json()["detail"] == OUTSIDE
    assert await session.scalar(select(Event).where(Event.title == "Rally nowhere")) is None


async def test_a_target_cannot_be_set_on_a_ward_outside_the_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    outside = await _elsewhere(session, world)

    refused = await client.post(
        "/api/targets/",
        headers=world.headers("manager"),
        json={"campaign": str(world.campaign.id), "ward": str(outside.id)},
    )

    assert refused.status_code == 400
    assert refused.json()["detail"] == OUTSIDE
    assert await session.scalar(select(Target).where(Target.ward_id == outside.id)) is None


async def test_a_team_login_cannot_be_given_a_ward_outside_the_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    outside = await _elsewhere(session, world)

    refused = await client.post(
        "/api/users/",
        headers=world.headers("manager"),
        json={
            "username": "strayboots",
            "role": "mobilizer",
            "campaign": str(world.campaign.id),
            "ward": str(outside.id),
        },
    )

    assert refused.status_code == 400
    assert refused.json()["detail"] == OUTSIDE
    assert await session.scalar(select(User).where(User.username == "strayboots")) is None


async def test_a_centre_has_to_be_in_the_ward_it_is_named_with(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """Both wards are the campaign's; the centre belongs to only one of them."""
    refused = await client.post(
        "/api/events/",
        headers=world.headers("manager"),
        json={
            "campaign": str(world.campaign.id),
            "ward": str(world.other_ward.id),
            "registration_centre": str(world.centre.id),
            "title": "Crossed wires",
            "venue": "Githurai",
        },
    )

    assert refused.status_code == 400
    assert refused.json()["detail"] == "That registration centre is not in that ward."
    assert await session.scalar(select(Event).where(Event.title == "Crossed wires")) is None


async def test_a_ward_race_with_no_centres_loaded_can_still_staff_its_own_ward(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """A ward race with no centres imported yet still staffs its own ward."""
    from backend.services.targets import generate_targets

    head = await _admin(session, client)
    bare = Ward(
        constituency_id=world.constituency.id,
        name="Kahawa",
        code="1394",
        registered_voters=18_000,
    )
    session.add(bare)
    await session.commit()
    mca = await make_user(session, username="mca", role=UserRole.CANDIDATE)
    race = Campaign(title="Kahawa MCA", office_level=OfficeLevel.WARD, ward_id=bare.id)
    session.add(race)
    await session.flush()
    session.add(CampaignMember(campaign_id=race.id, user_id=mca.id, role=UserRole.CANDIDATE))
    await session.commit()
    summary = await generate_targets(session, race)
    assert summary.units == 0, "the premise: no centres, so no targets"

    made = await client.post(
        "/api/admin/users/",
        headers=head,
        json={
            "username": "kahawaboots",
            "role": "mobilizer",
            "campaign": str(race.id),
            "ward": str(bare.id),
        },
    )

    assert made.status_code == 201, made.text


# ------------------------------------ centres, the console list, the register


async def test_a_team_login_cannot_be_given_a_centre_outside_its_ward(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """The ward is the campaign's; the centre sits in the other ward."""
    refused = await client.post(
        "/api/users/",
        headers=world.headers("manager"),
        json={
            "username": "crossedboots",
            "role": "mobilizer",
            "campaign": str(world.campaign.id),
            "ward": str(world.other_ward.id),
            "registration_centre": str(world.centre.id),
        },
    )

    assert refused.status_code == 400
    assert refused.json()["detail"] == "That registration centre is not in that ward."
    assert await session.scalar(select(User).where(User.username == "crossedboots")) is None


async def test_an_unknown_centre_on_a_team_login_is_refused_not_a_500(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    refused = await client.post(
        "/api/users/",
        headers=world.headers("manager"),
        json={
            "username": "ghostcentre",
            "role": "mobilizer",
            "campaign": str(world.campaign.id),
            "ward": str(world.ward.id),
            "registration_centre": str(uuid.uuid4()),
        },
    )

    assert refused.status_code == 400
    assert await session.scalar(select(User).where(User.username == "ghostcentre")) is None


async def test_the_console_offers_a_bare_ward_race_its_own_ward(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """The ward picker lists what the API accepts, centres or not."""
    head = await _admin(session, client)
    bare = Ward(
        constituency_id=world.constituency.id,
        name="Kahawa West",
        code="1395",
        registered_voters=17_000,
    )
    session.add(bare)
    await session.commit()
    mca = await make_user(session, username="mcawest", role=UserRole.CANDIDATE)
    race = Campaign(title="Kahawa West MCA", office_level=OfficeLevel.WARD, ward_id=bare.id)
    session.add(race)
    await session.flush()
    session.add(CampaignMember(campaign_id=race.id, user_id=mca.id, role=UserRole.CANDIDATE))
    await session.commit()

    body = (await client.get(f"/api/admin/campaigns/{race.id}/", headers=head)).json()

    assert [w["name"] for w in body["wards"]] == ["Kahawa West"]


async def test_the_console_lists_exactly_the_wards_the_api_accepts(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)
    outside = await _elsewhere(session, world)

    body = (await client.get(f"/api/admin/campaigns/{world.campaign.id}/", headers=head)).json()

    listed = {w["id"] for w in body["wards"]}
    assert listed == {str(world.ward.id), str(world.other_ward.id)}
    assert str(outside.id) not in listed


async def test_a_mobilizer_s_supporter_lands_in_their_own_ward_when_none_is_named(
    client: httpx.AsyncClient, world: World
) -> None:
    """Filed under no ward, it would vanish from the only list they can read."""
    made = await client.post(
        "/api/supporters/",
        headers=world.headers("mobilizer"),
        json={
            "campaign": str(world.campaign.id),
            "full_name": "Walk Up",
            "phone": "+254700222444",
            "support_level": "supporter",
            "consent_given": True,
        },
    )

    assert made.status_code == 201, made.text
    assert made.json()["ward"] == str(world.mobilizer.ward_id)
    listed = (await client.get("/api/supporters/", headers=world.headers("mobilizer"))).json()
    assert "Walk Up" in {s["full_name"] for s in listed}


async def test_an_unknown_campaign_reads_as_not_found_in_the_console(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)

    missing = await client.get(f"/api/admin/campaigns/{uuid.uuid4()}/", headers=head)

    assert missing.status_code == 404
