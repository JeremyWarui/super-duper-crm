"""Reading and editing vote targets through the API."""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Target
from tests.conftest import World


async def _targets(client: httpx.AsyncClient, world: World, role: str = "manager") -> list[dict]:
    response = await client.get(
        f"/api/targets/?campaign={world.campaign.id}", headers=world.headers(role)
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_listing_targets_needs_a_token(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/targets/")).status_code == 401


async def test_a_target_names_its_unit_and_carries_its_register(
    client: httpx.AsyncClient, world: World
) -> None:
    rows = await _targets(client, world)

    zimmerman = next(r for r in rows if r["ward_name"] == "Zimmerman")
    assert zimmerman["ward"] == str(world.ward.id)
    assert zimmerman["centre_name"] is None
    assert zimmerman["registered_voters"] == 30_701
    assert zimmerman["projected_turnout_pct"] == "60.00"
    assert zimmerman["votes_needed"] == 9_211
    assert zimmerman["votes_committed"] == 0
    assert zimmerman["votes_remaining"] == 9_211
    assert zimmerman["progress_pct"] == 0.0


async def test_targets_come_back_in_ward_order(client: httpx.AsyncClient, world: World) -> None:
    assert [r["ward_name"] for r in await _targets(client, world)] == ["Githurai", "Zimmerman"]


async def test_a_candidate_may_read_targets_but_not_change_them(
    client: httpx.AsyncClient, world: World
) -> None:
    rows = await _targets(client, world, role="candidate")
    target_id = rows[0]["id"]

    response = await client.patch(
        f"/api/targets/{target_id}/",
        headers=world.headers("candidate"),
        json={"projected_turnout_pct": 70},
    )

    assert response.status_code == 403


async def test_moving_the_turnout_slider_recomputes_the_win_number(
    client: httpx.AsyncClient, world: World
) -> None:
    zimmerman = next(r for r in await _targets(client, world) if r["ward_name"] == "Zimmerman")

    response = await client.patch(
        f"/api/targets/{zimmerman['id']}/",
        headers=world.headers("manager"),
        json={"projected_turnout_pct": 70},
    )

    assert response.status_code == 200
    assert response.json()["votes_needed"] == 10_746


async def test_the_client_cannot_set_the_win_number_itself(
    client: httpx.AsyncClient, world: World
) -> None:
    zimmerman = next(r for r in await _targets(client, world) if r["ward_name"] == "Zimmerman")

    response = await client.patch(
        f"/api/targets/{zimmerman['id']}/",
        headers=world.headers("manager"),
        json={"votes_needed": 1},
    )

    assert response.status_code == 400


async def test_committing_votes_moves_the_progress(client: httpx.AsyncClient, world: World) -> None:
    zimmerman = next(r for r in await _targets(client, world) if r["ward_name"] == "Zimmerman")

    body = (
        await client.patch(
            f"/api/targets/{zimmerman['id']}/",
            headers=world.headers("manager"),
            json={"votes_committed": 4_606},
        )
    ).json()

    assert body["votes_committed"] == 4_606
    assert body["votes_remaining"] == 4_605
    assert body["progress_pct"] == 50.0


async def test_a_turnout_over_a_hundred_percent_is_refused(
    client: httpx.AsyncClient, world: World
) -> None:
    zimmerman = next(r for r in await _targets(client, world) if r["ward_name"] == "Zimmerman")

    response = await client.patch(
        f"/api/targets/{zimmerman['id']}/",
        headers=world.headers("manager"),
        json={"projected_turnout_pct": 140},
    )

    assert response.status_code == 400


async def test_a_centre_target_names_the_centre(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    response = await client.post(
        "/api/targets/",
        headers=world.headers("manager"),
        json={
            "campaign": str(world.campaign.id),
            "ward": str(world.ward.id),
            "registration_centre": str(world.centre.id),
            "projected_turnout_pct": 60,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["centre_name"] == "Zimmerman Primary"
    assert body["registered_voters"] == 2_500
    assert body["votes_needed"] == 751


async def test_a_mobilizer_sees_only_their_own_ward_s_target(
    client: httpx.AsyncClient, world: World
) -> None:
    rows = await _targets(client, world, role="mobilizer")
    assert [r["ward_name"] for r in rows] == ["Zimmerman"]


async def test_a_mobilizer_may_not_change_a_target(client: httpx.AsyncClient, world: World) -> None:
    zimmerman = next(r for r in await _targets(client, world) if r["ward_name"] == "Zimmerman")

    response = await client.patch(
        f"/api/targets/{zimmerman['id']}/",
        headers=world.headers("mobilizer"),
        json={"votes_committed": 100},
    )

    assert response.status_code == 403


async def test_an_unknown_target_is_404(client: httpx.AsyncClient, world: World) -> None:
    response = await client.patch(
        "/api/targets/00000000-0000-0000-0000-000000000009/",
        headers=world.headers("manager"),
        json={"votes_committed": 1},
    )
    assert response.status_code == 404


async def test_deleting_a_target_removes_it(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    zimmerman = next(r for r in await _targets(client, world) if r["ward_name"] == "Zimmerman")

    response = await client.delete(
        f"/api/targets/{zimmerman['id']}/", headers=world.headers("manager")
    )

    assert response.status_code == 204
    remaining = (await session.execute(select(Target))).scalars().all()
    assert len(remaining) == 1
