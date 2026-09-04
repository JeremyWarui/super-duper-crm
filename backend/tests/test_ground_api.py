"""Mobilizers, events and the supporter register: the ground team's routes."""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Event, EventStatus, Mobilizer, Supporter
from tests.conftest import World

# ---------------------------------------------------------------- mobilizers


async def test_listing_mobilizers_needs_a_token(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/mobilizers/")).status_code == 401


async def test_a_mobilizer_row_names_its_ward(client: httpx.AsyncClient, world: World) -> None:
    body = (await client.get("/api/mobilizers/", headers=world.headers("manager"))).json()

    assert len(body) == 1
    assert body[0]["full_name"] == "Juma Otieno"
    assert body[0]["ward"] == str(world.ward.id)
    assert body[0]["ward_name"] == "Zimmerman"
    assert body[0]["user"] == str(world.mobilizer_user.id)


async def test_a_manager_can_assign_a_mobilizer_to_a_ward(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    response = await client.post(
        "/api/mobilizers/",
        headers=world.headers("manager"),
        json={
            "campaign": str(world.campaign.id),
            "ward": str(world.other_ward.id),
            "full_name": "Wanjiku Njeri",
            "phone": "+254700111222",
        },
    )

    assert response.status_code == 201
    assert response.json()["ward_name"] == "Githurai"
    assert await session.scalar(select(Mobilizer).where(Mobilizer.full_name == "Wanjiku Njeri"))


async def test_a_mobilizer_without_a_name_is_refused(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post(
        "/api/mobilizers/",
        headers=world.headers("manager"),
        json={"campaign": str(world.campaign.id), "ward": str(world.ward.id), "full_name": ""},
    )
    assert response.status_code == 400


async def test_a_candidate_may_not_assign_a_mobilizer(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post(
        "/api/mobilizers/",
        headers=world.headers("candidate"),
        json={
            "campaign": str(world.campaign.id),
            "ward": str(world.ward.id),
            "full_name": "Wanjiku Njeri",
        },
    )
    assert response.status_code == 403


async def test_a_mobilizer_may_not_assign_another_mobilizer(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post(
        "/api/mobilizers/",
        headers=world.headers("mobilizer"),
        json={
            "campaign": str(world.campaign.id),
            "ward": str(world.ward.id),
            "full_name": "Wanjiku Njeri",
        },
    )
    assert response.status_code == 403


# -------------------------------------------------------------------- events


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
    body.update(overrides)
    return await client.post("/api/events/", headers=world.headers(role), json=body)


async def test_a_manager_can_schedule_an_event(client: httpx.AsyncClient, world: World) -> None:
    response = await _schedule(client, world, "manager")

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Zimmerman town hall"
    assert body["ward_name"] == "Zimmerman"
    assert body["status"] == "planned"
    assert body["scheduled_date"].startswith("2027-06-12")
    assert body["number_reached"] == 0
    assert body["turnout_pct"] == 0.0


async def test_a_date_without_a_time_is_accepted(client: httpx.AsyncClient, world: World) -> None:
    response = await _schedule(client, world, "manager", scheduled_date="2027-06-12")
    assert response.status_code == 201


async def test_a_mobilizer_can_schedule_in_their_own_ward(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await _schedule(client, world, "mobilizer")
    assert response.status_code == 201


async def test_a_mobilizer_s_event_is_credited_to_them_without_being_asked(
    client: httpx.AsyncClient, world: World
) -> None:
    body = (await _schedule(client, world, "mobilizer")).json()
    assert body["mobilizer"] == str(world.mobilizer.id)


async def test_a_mobilizer_cannot_schedule_in_another_ward(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await _schedule(client, world, "mobilizer", ward=str(world.other_ward.id))
    assert response.status_code == 403


async def test_a_candidate_may_not_schedule_an_event(
    client: httpx.AsyncClient, world: World
) -> None:
    assert (await _schedule(client, world, "candidate")).status_code == 403


async def test_recording_attendance_closes_the_event(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    event_id = (await _schedule(client, world, "manager")).json()["id"]

    response = await client.post(
        f"/api/events/{event_id}/record/",
        headers=world.headers("mobilizer"),
        json={"number_reached": 400, "number_attended": 300},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "done"
    assert body["number_reached"] == 400
    assert body["number_attended"] == 300
    assert body["turnout_pct"] == 75.0


async def test_attendance_cannot_exceed_the_number_reached(
    client: httpx.AsyncClient, world: World
) -> None:
    event_id = (await _schedule(client, world, "manager")).json()["id"]

    response = await client.post(
        f"/api/events/{event_id}/record/",
        headers=world.headers("mobilizer"),
        json={"number_reached": 100, "number_attended": 200},
    )

    assert response.status_code == 400
    assert "exceed" in response.json()["detail"]


async def test_recording_needs_both_numbers(client: httpx.AsyncClient, world: World) -> None:
    event_id = (await _schedule(client, world, "manager")).json()["id"]

    response = await client.post(
        f"/api/events/{event_id}/record/",
        headers=world.headers("manager"),
        json={"number_reached": 100},
    )

    assert response.status_code == 400
    assert "number_attended" in response.json()["detail"]


async def test_a_mobilizer_cannot_record_another_ward_s_event(
    client: httpx.AsyncClient, world: World
) -> None:
    event_id = (await _schedule(client, world, "manager", ward=str(world.other_ward.id))).json()[
        "id"
    ]

    response = await client.post(
        f"/api/events/{event_id}/record/",
        headers=world.headers("mobilizer"),
        json={"number_reached": 10, "number_attended": 5},
    )

    assert response.status_code == 403


async def test_a_mobilizer_lists_only_their_own_ward_s_events(
    client: httpx.AsyncClient, world: World
) -> None:
    await _schedule(client, world, "manager")
    await _schedule(client, world, "manager", ward=str(world.other_ward.id), title="Githurai rally")

    body = (await client.get("/api/events/", headers=world.headers("mobilizer"))).json()

    assert [e["ward_name"] for e in body] == ["Zimmerman"]


async def test_events_are_listed_newest_first(client: httpx.AsyncClient, world: World) -> None:
    await _schedule(client, world, "manager", title="Earlier", scheduled_date="2027-06-01")
    await _schedule(client, world, "manager", title="Later", scheduled_date="2027-07-01")

    body = (await client.get("/api/events/", headers=world.headers("manager"))).json()

    assert [e["title"] for e in body] == ["Later", "Earlier"]


async def test_deleting_an_event_removes_it(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    event_id = (await _schedule(client, world, "manager")).json()["id"]

    response = await client.delete(f"/api/events/{event_id}/", headers=world.headers("manager"))

    assert response.status_code == 204
    assert (await session.execute(select(Event))).scalars().all() == []


async def test_an_event_status_that_is_not_a_status_is_refused(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await _schedule(client, world, "manager", status="maybe")
    assert response.status_code == 400


# ---------------------------------------------------------------- supporters


def _supporter(world: World, **overrides) -> dict:
    body = {
        "campaign": str(world.campaign.id),
        "ward": str(world.ward.id),
        "full_name": "Wanjiku Njeri",
        "phone": "+254700333444",
        "consent_given": True,
    }
    body.update(overrides)
    return body


async def test_a_mobilizer_can_register_a_supporter(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post(
        "/api/supporters/", headers=world.headers("mobilizer"), json=_supporter(world)
    )

    assert response.status_code == 201
    body = response.json()
    assert body["full_name"] == "Wanjiku Njeri"
    assert body["support_level"] == "undecided"
    assert body["mobilizer"] == str(world.mobilizer.id)


async def test_signing_up_without_consent_is_refused(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post(
        "/api/supporters/",
        headers=world.headers("mobilizer"),
        json=_supporter(world, consent_given=False),
    )

    assert response.status_code == 400
    assert "Consent" in response.json()["detail"]


async def test_anyone_may_sign_themselves_up_without_an_account(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    response = await client.post("/api/supporters/", json=_supporter(world))

    assert response.status_code == 201
    assert await session.scalar(select(Supporter).where(Supporter.full_name == "Wanjiku Njeri"))


async def test_the_register_is_not_readable_without_an_account(
    client: httpx.AsyncClient, world: World
) -> None:
    assert (await client.get("/api/supporters/")).status_code == 401


async def test_a_candidate_may_not_read_the_supporter_register(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.get("/api/supporters/", headers=world.headers("candidate"))
    assert response.status_code == 403


async def test_a_manager_reads_the_whole_register(client: httpx.AsyncClient, world: World) -> None:
    await client.post("/api/supporters/", headers=world.headers("manager"), json=_supporter(world))
    await client.post(
        "/api/supporters/",
        headers=world.headers("manager"),
        json=_supporter(world, ward=str(world.other_ward.id), full_name="Otieno K."),
    )

    body = (await client.get("/api/supporters/", headers=world.headers("manager"))).json()

    assert len(body) == 2


async def test_a_mobilizer_reads_only_their_own_ward_s_supporters(
    client: httpx.AsyncClient, world: World
) -> None:
    await client.post("/api/supporters/", headers=world.headers("manager"), json=_supporter(world))
    await client.post(
        "/api/supporters/",
        headers=world.headers("manager"),
        json=_supporter(world, ward=str(world.other_ward.id), full_name="Otieno K."),
    )

    body = (await client.get("/api/supporters/", headers=world.headers("mobilizer"))).json()

    assert [s["full_name"] for s in body] == ["Wanjiku Njeri"]


async def test_a_mobilizer_cannot_register_someone_in_another_ward(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post(
        "/api/supporters/",
        headers=world.headers("mobilizer"),
        json=_supporter(world, ward=str(world.other_ward.id)),
    )
    assert response.status_code == 403


async def test_a_supporter_can_be_erased_on_request(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    created = (
        await client.post(
            "/api/supporters/", headers=world.headers("manager"), json=_supporter(world)
        )
    ).json()

    response = await client.delete(
        f"/api/supporters/{created['id']}/", headers=world.headers("manager")
    )

    assert response.status_code == 204
    assert (await session.execute(select(Supporter))).scalars().all() == []


async def test_erasing_a_supporter_needs_an_account(
    client: httpx.AsyncClient, world: World
) -> None:
    created = (
        await client.post(
            "/api/supporters/", headers=world.headers("manager"), json=_supporter(world)
        )
    ).json()

    assert (await client.delete(f"/api/supporters/{created['id']}/")).status_code == 401


async def test_a_done_event_reports_its_turnout(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    event = Event(
        campaign_id=world.campaign.id,
        ward_id=world.ward.id,
        title="Zimmerman rally",
        status=EventStatus.DONE,
        number_reached=200,
        number_attended=150,
    )
    session.add(event)
    await session.commit()

    body = (await client.get("/api/events/", headers=world.headers("manager"))).json()

    assert body[0]["turnout_pct"] == 75.0
