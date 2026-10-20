"""An MCA race counts supporters per registration centre, the same on every screen."""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Campaign, RegistrationCentre, Supporter, SupportLevel, UserRole
from backend.services import admin
from backend.services.accounts import add_member
from backend.services.strategy import read_strategy
from backend.services.targets import generate_targets
from tests.conftest import World
from tests.factories import auth, make_campaign, make_user, sign_in


async def _mca(session: AsyncSession, client: httpx.AsyncClient, world: World, ward=None):
    """An MCA race with its targets built, Zimmerman by default, and a signed-in manager on it."""
    mca = await make_campaign(session, ward or world.ward)
    await generate_targets(session, mca)
    manager = await make_user(session, username="otieno", role=UserRole.MANAGER)
    await add_member(session, mca.id, manager)
    await session.commit()
    return mca, auth(await sign_in(client, "otieno"))


async def test_a_supporter_with_no_centre_counts_nowhere_until_placed(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    mca, headers = await _mca(session, client, world)
    supporter = Supporter(
        campaign_id=mca.id,
        ward_id=world.ward.id,
        full_name="Wanjiku Njeri",
        support_level=SupportLevel.SUPPORTER,
    )
    session.add(supporter)
    await session.commit()

    before = await read_strategy(session, campaign_ids=frozenset({mca.id}))
    console = (await admin.campaigns(session, mca.id))[0]
    placed = await client.patch(
        f"/api/supporters/{supporter.id}/",
        headers=headers,
        json={"registration_centre": str(world.centre.id)},
    )
    after = await read_strategy(session, campaign_ids=frozenset({mca.id}))

    assert (before.committed, console.votes_committed) == (0, 0)
    assert "1 supporter needs a centre" in [n.title for n in before.notes]
    assert placed.status_code == 200
    assert [(u.unit, u.committed) for u in after.units] == [("Zimmerman Primary", 1)]


async def test_a_supporter_is_not_placed_at_a_centre_with_no_target(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    mca, headers = await _mca(session, client, world)
    later = RegistrationCentre(ward=world.ward, name="Zimmerman Secondary", code="003")
    supporter = Supporter(
        campaign_id=mca.id,
        ward_id=world.ward.id,
        full_name="Wanjiku Njeri",
        support_level=SupportLevel.SUPPORTER,
    )
    session.add_all([later, supporter])
    await session.commit()

    response = await client.patch(
        f"/api/supporters/{supporter.id}/",
        headers=headers,
        json={"registration_centre": str(later.id)},
    )

    assert response.status_code == 400


async def test_supporters_at_a_centre_whose_target_is_deleted_are_flagged(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    mca, headers = await _mca(session, client, world)
    session.add(
        Supporter(
            campaign_id=mca.id,
            ward_id=world.ward.id,
            registration_centre_id=world.centre.id,
            full_name="Wanjiku Njeri",
            support_level=SupportLevel.SUPPORTER,
        )
    )
    await session.commit()
    target = (await client.get(f"/api/targets/?campaign={mca.id}", headers=headers)).json()[0]

    await client.delete(f"/api/targets/{target['id']}/", headers=headers)
    notes = (await read_strategy(session, campaign_ids=frozenset({mca.id}))).notes

    assert "1 supporter needs a centre" in [n.title for n in notes]


async def test_an_mca_race_refuses_a_ward_target_beside_its_centre_targets(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    mca, headers = await _mca(session, client, world)

    response = await client.post(
        "/api/targets/", headers=headers, json={"campaign": str(mca.id), "ward": str(world.ward.id)}
    )

    assert response.status_code == 400


async def test_a_unit_with_a_target_takes_no_second_one(
    client: httpx.AsyncClient, world: World
) -> None:
    again = await client.post(
        "/api/targets/",
        headers=world.headers("manager"),
        json={"campaign": str(world.campaign.id), "ward": str(world.ward.id)},
    )

    assert (again.status_code, again.json()["detail"]) == (400, "That unit already has a target.")


def test_a_campaign_s_seat_is_a_seat_from_construction() -> None:
    assert Campaign(seat="senator", office_level="county").seat.label == "Senator"
    assert Campaign(office_level="ward").seat.label == "MCA"
