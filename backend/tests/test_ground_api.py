"""The ground team's routes: mobilizers, events and the supporter register."""

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Event, EventStatus, Mobilizer, Supporter, UserRole
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


@pytest.mark.parametrize("path", ["/api/mobilizers/", "/api/events/", "/api/supporters/"])
async def test_the_ground_routes_need_a_token(
    client: httpx.AsyncClient, session: AsyncSession, world: World, path: str
) -> None:
    assert (await client.get(path)).status_code == 401
    assert (await client.post(path, json=_supporter(world))).status_code == 401
    assert await session.scalar(select(func.count()).select_from(Supporter)) == 0


async def test_a_mobilizer_row_names_its_ward_and_login(
    client: httpx.AsyncClient, world: World
) -> None:
    (row,) = (await client.get("/api/mobilizers/", headers=world.headers("manager"))).json()

    assert row["full_name"] == "Juma Otieno"
    assert (row["ward"], row["ward_name"]) == (str(world.ward.id), "Zimmerman")
    assert row["user"] == str(world.mobilizer_user.id)


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


async def test_a_mobilizer_without_a_name_is_refused(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post(
        "/api/mobilizers/", headers=world.headers("manager"), json=_ground(world, full_name="")
    )
    assert response.status_code == 400


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


async def test_a_free_mobilizer_login_is_put_on_the_ground_and_the_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    spare = await make_user(session, username="spare", role=UserRole.MOBILIZER)

    response = await client.post(
        "/api/mobilizers/",
        headers=world.headers("manager"),
        json=_ground(world, user=str(spare.id)),
    )

    assert response.status_code == 201, response.text
    assert response.json()["user"] == str(spare.id)
    seen = await client.get("/api/campaigns/", headers=auth(await sign_in(client, "spare")))
    assert [c["id"] for c in seen.json()] == [str(world.campaign.id)]


async def test_a_login_put_on_the_ground_without_a_phone_keeps_the_login_s_phone(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    spare = await make_user(
        session, username="spare", role=UserRole.MOBILIZER, phone="+254700999888"
    )

    response = await client.post(
        "/api/mobilizers/",
        headers=world.headers("manager"),
        json=_ground(world, user=str(spare.id), phone=""),
    )

    assert response.status_code == 201, response.text
    assert (response.json()["full_name"], response.json()["phone"]) == (
        "Wanjiku Njeri",
        "+254700999888",
    )


@pytest.mark.parametrize(
    ("who", "code", "message"),
    [
        ("candidate", 400, "jane is not a mobilizer."),
        ("on-the-ground", 409, "juma is already on the ground somewhere."),
        ("on-a-rival-campaign", 400, "theirs is already on Rival for Githurai"),
    ],
)
async def test_a_login_that_cannot_go_on_the_ground_here_is_refused(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    who: str,
    code: int,
    message: str,
) -> None:
    if who == "on-a-rival-campaign":
        from backend.services.accounts import add_member

        rival = await make_rival_campaign(session, world.other_ward)
        login = await make_user(session, username="theirs", role=UserRole.MOBILIZER)
        await add_member(session, rival.id, login)
        await session.commit()
    else:
        login = world.candidate if who == "candidate" else world.mobilizer_user

    response = await client.post(
        "/api/mobilizers/",
        headers=world.headers("manager"),
        json=_ground(world, user=str(login.id), full_name="Planted"),
    )

    assert response.status_code == code
    assert message in response.json()["detail"]
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


async def test_a_mobilizer_s_event_in_their_ward_is_credited_to_them(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await _schedule(client, world, "mobilizer")

    assert response.status_code == 201
    assert response.json()["mobilizer"] == str(world.mobilizer.id)


@pytest.mark.parametrize(
    ("role", "overrides", "code"),
    [
        ("mobilizer", {"ward": "other"}, 403),
        ("candidate", {}, 403),
        ("manager", {"status": "maybe"}, 400),
    ],
)
async def test_an_event_that_cannot_be_scheduled_is_refused(
    client: httpx.AsyncClient, world: World, role: str, overrides: dict, code: int
) -> None:
    if overrides.get("ward") == "other":
        overrides = {"ward": str(world.other_ward.id)}

    assert (await _schedule(client, world, role, **overrides)).status_code == code


async def test_an_event_cannot_name_another_campaign_s_mobilizer(
    client: httpx.AsyncClient, new_manager: dict, world: World
) -> None:
    setup = await client.post(
        "/api/campaigns/setup/",
        headers=new_manager,
        json={
            "title": "Rival for Githurai",
            "office_level": "ward",
            "ward": str(world.other_ward.id),
            "new_candidate": {"username": "theirs"},
        },
    )

    response = await client.post(
        "/api/events/",
        headers=new_manager,
        json={
            "campaign": setup.json()["id"],
            "ward": str(world.other_ward.id),
            "mobilizer": str(world.mobilizer.id),
            "title": "Borrowed Organizer",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "No such mobilizer on this campaign."


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


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"number_reached": 100, "number_attended": 200}, "exceed"),
        ({"number_reached": 100}, "number_attended"),
    ],
)
async def test_attendance_that_does_not_add_up_is_refused(
    client: httpx.AsyncClient, world: World, body: dict, message: str
) -> None:
    event_id = (await _schedule(client, world, "manager")).json()["id"]

    response = await client.post(
        f"/api/events/{event_id}/record/", headers=world.headers("manager"), json=body
    )

    assert response.status_code == 400
    assert message in response.json()["detail"]


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


async def test_events_are_listed_newest_first_with_their_turnout(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await _schedule(client, world, "manager", title="Earlier", scheduled_date="2027-06-01")
    await _schedule(client, world, "manager", title="Later", scheduled_date="2027-07-01")
    session.add(
        Event(
            campaign_id=world.campaign.id,
            ward_id=world.ward.id,
            title="Undated rally",
            status=EventStatus.DONE,
            number_reached=200,
            number_attended=150,
        )
    )
    await session.commit()

    body = (await client.get("/api/events/", headers=world.headers("manager"))).json()

    assert [e["title"] for e in body] == ["Later", "Earlier", "Undated rally"]
    assert body[-1]["turnout_pct"] == 75.0


async def test_deleting_an_event_removes_it(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    event_id = (await _schedule(client, world, "manager")).json()["id"]

    response = await client.delete(f"/api/events/{event_id}/", headers=world.headers("manager"))

    assert response.status_code == 204
    assert await session.scalar(select(func.count()).select_from(Event)) == 0


async def test_a_mobilizer_registers_a_supporter_credited_to_them(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post(
        "/api/supporters/", headers=world.headers("mobilizer"), json=_supporter(world)
    )

    assert response.status_code == 201
    body = response.json()
    assert (body["full_name"], body["support_level"]) == ("Wanjiku Njeri", "undecided")
    assert body["mobilizer"] == str(world.mobilizer.id)


@pytest.mark.parametrize(
    ("role", "overrides", "code"),
    [
        ("mobilizer", {"consent_given": False}, 400),
        ("mobilizer", {"ward": "other"}, 403),
    ],
)
async def test_a_supporter_that_cannot_be_registered_is_refused(
    client: httpx.AsyncClient, world: World, role: str, overrides: dict, code: int
) -> None:
    if overrides.get("ward") == "other":
        overrides = {"ward": str(world.other_ward.id)}

    response = await client.post(
        "/api/supporters/", headers=world.headers(role), json=_supporter(world, **overrides)
    )

    assert response.status_code == code


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
        json=_supporter(world, ward=str(world.other_ward.id), full_name="Otieno K."),
    )

    whole = (await client.get("/api/supporters/", headers=head)).json()
    own = (await client.get("/api/supporters/", headers=world.headers("mobilizer"))).json()
    candidate = await client.get("/api/supporters/", headers=world.headers("candidate"))

    assert len(whole) == 2
    assert [s["full_name"] for s in own] == ["Wanjiku Njeri"]
    assert candidate.status_code == 403


async def test_a_supporter_is_erased_on_request_by_a_signed_in_team_member(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    created = (
        await client.post(
            "/api/supporters/", headers=world.headers("manager"), json=_supporter(world)
        )
    ).json()

    anonymous = await client.delete(f"/api/supporters/{created['id']}/")
    erased = await client.delete(
        f"/api/supporters/{created['id']}/", headers=world.headers("manager")
    )

    assert (anonymous.status_code, erased.status_code) == (401, 204)
    assert await session.scalar(select(func.count()).select_from(Supporter)) == 0
