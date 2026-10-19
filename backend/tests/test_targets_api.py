"""Reading and editing vote targets through the API."""

import httpx

from tests.conftest import World


async def _targets(client: httpx.AsyncClient, world: World, role: str = "manager") -> list[dict]:
    response = await client.get(
        f"/api/targets/?campaign={world.campaign.id}", headers=world.headers(role)
    )
    assert response.status_code == 200, response.text
    return response.json()


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


async def test_a_mobilizer_may_not_change_a_target(client: httpx.AsyncClient, world: World) -> None:
    zimmerman = next(r for r in await _targets(client, world) if r["ward_name"] == "Zimmerman")

    response = await client.patch(
        f"/api/targets/{zimmerman['id']}/",
        headers=world.headers("mobilizer"),
        json={"votes_committed": 100},
    )

    assert response.status_code == 403
