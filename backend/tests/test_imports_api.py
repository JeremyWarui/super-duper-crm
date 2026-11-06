"""Boundary and voter register imports from the console, and refreshing targets after them."""

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import ImportChange, Ward
from backend.services.imports import BOUNDARY_COLUMNS
from tests.conftest import World

pytestmark = pytest.mark.party_only

HEADER = ",".join(BOUNDARY_COLUMNS) + "\n"
ROYSAMBU = "047,Nairobi City,279,Roysambu"


def boundaries(*rows: str) -> str:
    return HEADER + "".join(f"{row}\n" for row in rows)


async def send(client, headers, kind: str, csv: str, **extra) -> httpx.Response:
    body = {"filename": f"{kind}.csv", "csv": csv, **extra}
    return await client.post(f"/api/admin/imports/{kind}/", json=body, headers=headers)


async def test_a_bad_row_writes_nothing(
    client: httpx.AsyncClient, admin_headers: dict, world: World, session: AsyncSession
) -> None:
    csv = boundaries(
        f"{ROYSAMBU},1391,Githurai West,,",
        f"{ROYSAMBU},1393,,,",
    )

    answer = await send(client, admin_headers, "boundaries", csv)

    assert answer.status_code == 400
    assert "Line 3: ward_name missing." in answer.json()["detail"]
    await session.refresh(world.other_ward)
    assert world.other_ward.name == "Githurai"
    assert await session.scalar(select(func.count(ImportChange.id))) == 0


async def test_a_referenced_ward_left_out_is_retired_not_deleted(
    client: httpx.AsyncClient, admin_headers: dict, world: World, session: AsyncSession
) -> None:
    answer = await send(
        client, admin_headers, "boundaries", boundaries(f"{ROYSAMBU},1391,Githurai,,")
    )

    assert answer.status_code == 200, answer.text
    assert {"level": "ward", "code": "1393", "change": "retired", "detail": "Zimmerman"} in (
        answer.json()["changes"]
    )
    kept = await session.scalar(select(Ward).where(Ward.code == "1393"))
    await session.refresh(kept)
    assert kept.retired is True
    picker = await client.get(
        f"/api/wards/?constituency={world.constituency.id}",
        headers=world.headers("manager"),
    )
    assert picker.status_code == 200, picker.text
    assert [w["name"] for w in picker.json()] == ["Githurai"]


async def test_re_importing_the_same_file_changes_nothing(
    client: httpx.AsyncClient, admin_headers: dict, world: World
) -> None:
    csv = boundaries(
        f"{ROYSAMBU},1391,Githurai West,,",
        f"{ROYSAMBU},1393,Zimmerman,001,Zimmerman Primary",
        f"{ROYSAMBU},1393,Zimmerman,002,Kamiti Corner",
    )
    first = await send(client, admin_headers, "boundaries", csv)
    again = await send(client, admin_headers, "boundaries", csv)

    assert first.json()["counts"] == {"renamed": 1, "created": 1}
    assert (again.json()["counts"], again.json()["changes"]) == ({}, [])


async def test_targets_keep_their_numbers_until_a_manager_refreshes_them(
    client: httpx.AsyncClient, admin_headers: dict, world: World
) -> None:
    manager = world.headers("manager")

    async def needed() -> tuple[int, int]:
        rows = (
            await client.get(f"/api/targets/?campaign={world.campaign.id}", headers=manager)
        ).json()
        row = next(t for t in rows if t["ward"] == str(world.ward.id))
        return row["registered_voters"], row["votes_needed"]

    before = await needed()
    register = "\n".join(
        [
            "county_code,ward_code,centre_code,registered_voters,turnout_pct",
            ",1393,,40000,",
            "047,,,,70",
        ]
    )

    imported = await send(client, admin_headers, "register", register)
    after_import = await needed()
    refreshed = await client.post(
        "/api/targets/refresh/", json={"campaign": str(world.campaign.id)}, headers=manager
    )
    after_refresh = await needed()

    assert imported.json()["counts"] == {"voters": 1, "turnout": 1}
    assert after_import == before
    assert refreshed.status_code == 200, refreshed.text
    # 40,000 voters at the target's own 60% turnout cast 24,000; a win is one more than half.
    assert after_refresh == (40_000, 12_001)
