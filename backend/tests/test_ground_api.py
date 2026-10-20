"""The ground team's routes: mobilizers, events and the supporter register."""

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Mobilizer, Supporter, UserRole
from tests.conftest import World
from tests.factories import auth, make_mobilizer, make_rival_campaign, make_user, sign_in


def _ground(world: World, **overrides) -> dict:
    body = {
        "campaign": str(world.campaign.id),
        "ward": str(world.other_ward.id),
        "full_name": "Wanjiku Njeri",
        "phone": "+254700111222",
    }
    return {**body, **overrides}


async def _schedule(
    client: httpx.AsyncClient, world: World, role: str, **overrides
) -> httpx.Response:
    body = {
        "campaign": str(world.campaign.id),
        "ward": str(world.ward.id),
        "title": "Zimmerman town hall",
        "venue": "Zimmerman social hall",
        "scheduled_date": "2027-06-12",
        "status": "planned",
    }
    return await client.post(
        "/api/events/", headers=world.headers(role), json={**body, **overrides}
    )


def _supporter(world: World, **overrides) -> dict:
    body = {
        "campaign": str(world.campaign.id),
        "ward": str(world.ward.id),
        "full_name": "Wanjiku Njeri",
        "phone": "+254700333444",
        "consent_given": True,
    }
    return {**body, **overrides}


@pytest.mark.parametrize("caller", ["manager", "candidate"])
async def test_the_manager_or_candidate_puts_somebody_on_the_ground_and_takes_them_off(
    client: httpx.AsyncClient, session: AsyncSession, world: World, caller: str
) -> None:
    head = auth(await sign_in(client, "juma"))

    made = await client.post("/api/mobilizers/", headers=world.headers(caller), json=_ground(world))
    gone = await client.delete(
        f"/api/mobilizers/{world.mobilizer.id}/", headers=world.headers(caller)
    )

    assert made.status_code == 201, made.text
    assert made.json()["ward_name"] == "Githurai"
    assert gone.status_code == 204
    assert await session.get(Mobilizer, world.mobilizer.id) is None
    assert (await client.get("/api/campaigns/", headers=head)).json() == []


async def test_a_mobilizer_neither_adds_nor_removes_ground_rows(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = world.headers("mobilizer")

    added = await client.post("/api/mobilizers/", headers=head, json=_ground(world))
    removed = await client.delete(f"/api/mobilizers/{world.mobilizer.id}/", headers=head)

    assert (added.status_code, removed.status_code) == (403, 403)
    assert await session.get(Mobilizer, world.mobilizer.id) is not None


@pytest.mark.parametrize("caller", ["candidate", "manager"])
async def test_nobody_touches_the_ground_team_of_somebody_else_s_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World, caller: str
) -> None:
    rival = await make_rival_campaign(session, world.other_ward)
    theirs = await make_mobilizer(session, rival, world.other_ward)

    planted = await client.post(
        "/api/mobilizers/",
        headers=world.headers(caller),
        json=_ground(world, campaign=str(rival.id), full_name="Planted"),
    )
    removed = await client.delete(f"/api/mobilizers/{theirs.id}/", headers=world.headers(caller))

    assert (planted.status_code, removed.status_code) == (404, 404)
    assert await session.get(Mobilizer, theirs.id) is not None
    assert await session.scalar(select(Mobilizer).where(Mobilizer.full_name == "Planted")) is None


async def test_a_manager_schedules_an_event(client: httpx.AsyncClient, world: World) -> None:
    response = await _schedule(client, world, "manager")

    assert response.status_code == 201
    body = response.json()
    assert (body["title"], body["ward_name"], body["status"]) == (
        "Zimmerman town hall",
        "Zimmerman",
        "planned",
    )
    assert body["scheduled_date"].startswith("2027-06-12")
    assert (body["number_reached"], body["turnout_pct"]) == (0, 0.0)


async def test_recording_attendance_closes_the_event(
    client: httpx.AsyncClient, world: World
) -> None:
    event_id = (await _schedule(client, world, "manager")).json()["id"]

    response = await client.post(
        f"/api/events/{event_id}/record/",
        headers=world.headers("mobilizer"),
        json={"number_reached": 400, "number_attended": 300},
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["number_reached"], body["number_attended"]) == ("done", 400, 300)
    assert body["turnout_pct"] == 75.0


async def test_a_mobilizer_reads_and_records_only_their_own_ward_s_events(
    client: httpx.AsyncClient, world: World
) -> None:
    await _schedule(client, world, "manager")
    other = await _schedule(
        client, world, "manager", ward=str(world.other_ward.id), title="Githurai rally"
    )

    listed = (await client.get("/api/events/", headers=world.headers("mobilizer"))).json()
    recorded = await client.post(
        f"/api/events/{other.json()['id']}/record/",
        headers=world.headers("mobilizer"),
        json={"number_reached": 10, "number_attended": 5},
    )

    assert [e["ward_name"] for e in listed] == ["Zimmerman"]
    assert recorded.status_code == 403


async def test_a_rival_campaign_cannot_write_into_this_register(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await make_user(session, username="rival", role=UserRole.MANAGER)

    response = await client.post(
        "/api/supporters/",
        headers=auth(await sign_in(client, "rival")),
        json=_supporter(world, full_name="Planted"),
    )

    assert response.status_code == 404
    assert await session.scalar(select(Supporter).where(Supporter.full_name == "Planted")) is None


async def test_the_register_is_whole_for_a_manager_one_ward_for_a_mobilizer_closed_to_a_candidate(
    client: httpx.AsyncClient, world: World
) -> None:
    head = world.headers("manager")
    await client.post("/api/supporters/", headers=head, json=_supporter(world))
    await client.post(
        "/api/supporters/",
        headers=head,
        json=_supporter(
            world, ward=str(world.other_ward.id), full_name="Otieno K.", phone="+254700555666"
        ),
    )

    whole = (await client.get("/api/supporters/", headers=head)).json()
    own = (await client.get("/api/supporters/", headers=world.headers("mobilizer"))).json()
    candidate = await client.get("/api/supporters/", headers=world.headers("candidate"))

    assert len(whole) == 2
    assert [s["full_name"] for s in own] == ["Wanjiku Njeri"]
    assert candidate.status_code == 403


@pytest.mark.parametrize(
    ("role", "codes"),
    [
        ("manager", (200, 201, 204)),
        ("mobilizer", (200, 201, 204)),
        ("candidate", (403, 403, 403)),
    ],
)
async def test_only_the_campaign_team_lists_adds_and_erases_supporters(
    client: httpx.AsyncClient, world: World, role: str, codes: tuple[int, int, int]
) -> None:
    head = world.headers(role)
    existing = (
        await client.post(
            "/api/supporters/", headers=world.headers("manager"), json=_supporter(world)
        )
    ).json()

    listed = await client.get("/api/supporters/", headers=head)
    added = await client.post(
        "/api/supporters/",
        headers=head,
        json=_supporter(world, full_name="Otieno K.", phone="+254700555666"),
    )
    erased = await client.delete(f"/api/supporters/{existing['id']}/", headers=head)

    assert (listed.status_code, added.status_code, erased.status_code) == codes


async def test_a_mobilizer_cannot_erase_a_supporter_with_no_ward(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    created = (
        await client.post(
            "/api/supporters/", headers=world.headers("manager"), json=_supporter(world, ward=None)
        )
    ).json()

    erased = await client.delete(
        f"/api/supporters/{created['id']}/", headers=world.headers("mobilizer")
    )

    assert created["ward"] is None
    assert erased.status_code == 403
    assert await session.scalar(select(func.count()).select_from(Supporter)) == 1


async def test_assigning_a_taken_ward_moves_its_mobilizer_off_and_null_removes(
    client: httpx.AsyncClient, world: World
) -> None:
    head = world.headers("manager")
    spare = (
        await client.post("/api/mobilizers/", headers=head, json=_ground(world, ward=None))
    ).json()

    swapped = await client.patch(
        f"/api/mobilizers/{spare['id']}/", headers=head, json={"ward": str(world.ward.id)}
    )
    listed = {
        m["id"]: m["ward_name"] for m in (await client.get("/api/mobilizers/", headers=head)).json()
    }
    removed = await client.patch(
        f"/api/mobilizers/{spare['id']}/", headers=head, json={"ward": None}
    )

    assert spare["ward"] is None
    assert swapped.status_code == 200, swapped.text
    assert listed == {spare["id"]: "Zimmerman", str(world.mobilizer.id): None}
    assert removed.json()["ward"] is None


async def test_a_mobilizer_with_no_ward_sees_nothing_of_the_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await client.post("/api/supporters/", headers=world.headers("manager"), json=_supporter(world))
    world.mobilizer.ward_id = None
    await session.commit()

    seen = await client.get("/api/supporters/", headers=world.headers("mobilizer"))
    events = await client.get("/api/events/", headers=world.headers("mobilizer"))

    assert (seen.json(), events.json()) == ([], [])


@pytest.mark.parametrize("with_centre", [False, True])
async def test_a_ward_with_a_mobilizer_takes_no_second_one(
    client: httpx.AsyncClient, world: World, with_centre: bool
) -> None:
    extra = {"registration_centre": str(world.centre.id)} if with_centre else {}

    response = await client.post(
        "/api/mobilizers/",
        headers=world.headers("manager"),
        json=_ground(world, ward=str(world.ward.id), **extra),
    )

    assert response.status_code == 400
