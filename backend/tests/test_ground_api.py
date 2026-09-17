"""Mobilizers, events and the supporter register: the ground team's routes."""

import httpx
import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    CampaignMember,
    Event,
    EventStatus,
    Mobilizer,
    Supporter,
    UserRole,
)
from tests.conftest import World
from tests.factories import auth, make_user, sign_in

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


async def test_a_candidate_can_assign_a_mobilizer_to_a_ward(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    response = await client.post(
        "/api/mobilizers/",
        headers=world.headers("candidate"),
        json={
            "campaign": str(world.campaign.id),
            "ward": str(world.other_ward.id),
            "full_name": "Wanjiku Njeri",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["ward_name"] == "Githurai"
    assert await session.scalar(select(Mobilizer).where(Mobilizer.full_name == "Wanjiku Njeri"))


async def test_a_candidate_can_take_a_mobilizer_off_the_ground(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    gone = await client.delete(
        f"/api/mobilizers/{world.mobilizer.id}/", headers=world.headers("candidate")
    )

    assert gone.status_code == 204
    assert await session.scalar(select(Mobilizer).where(Mobilizer.id == world.mobilizer.id)) is None


async def _rival_campaign(session: AsyncSession, world: World):
    """A campaign with its own candidate and mobilizer, that `world` is not on."""
    from backend.api.scope import add_member
    from backend.models import Campaign, OfficeLevel

    rival = await make_user(session, username="rival", role=UserRole.CANDIDATE)
    theirs = Campaign(
        title="Rival for Githurai",
        office_level=OfficeLevel.WARD,
        ward_id=world.other_ward.id,
    )
    session.add(theirs)
    await session.flush()
    await add_member(session, theirs.id, rival.id)
    ground = Mobilizer(
        campaign_id=theirs.id,
        ward_id=world.other_ward.id,
        full_name="Rival Organizer",
        phone="+254700333444",
    )
    session.add(ground)
    await session.commit()
    return theirs, ground


@pytest.mark.parametrize("caller", ["candidate", "manager"])
async def test_nobody_puts_a_mobilizer_on_somebody_else_s_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World, caller: str
) -> None:
    theirs, _ground = await _rival_campaign(session, world)

    refused = await client.post(
        "/api/mobilizers/",
        headers=world.headers(caller),
        json={
            "campaign": str(theirs.id),
            "ward": str(world.other_ward.id),
            "full_name": "Planted Organizer",
        },
    )

    assert refused.status_code == 404
    assert not await session.scalar(
        select(Mobilizer).where(Mobilizer.full_name == "Planted Organizer")
    )


@pytest.mark.parametrize("caller", ["candidate", "manager"])
async def test_nobody_takes_a_mobilizer_off_somebody_else_s_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World, caller: str
) -> None:
    _theirs, ground = await _rival_campaign(session, world)

    refused = await client.delete(f"/api/mobilizers/{ground.id}/", headers=world.headers(caller))

    assert refused.status_code == 404
    assert await session.scalar(select(Mobilizer).where(Mobilizer.id == ground.id)) is not None


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


async def test_a_mobilizer_may_not_take_a_mobilizer_off_the_ground(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    refused = await client.delete(
        f"/api/mobilizers/{world.mobilizer.id}/", headers=world.headers("mobilizer")
    )

    assert refused.status_code == 403
    assert await session.scalar(select(Mobilizer).where(Mobilizer.id == world.mobilizer.id))


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


async def test_the_register_cannot_be_written_to_without_an_account(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """The campaign is named in the body, so an open route is an open register."""
    response = await client.post("/api/supporters/", json=_supporter(world))

    assert response.status_code == 401
    assert not await session.scalar(select(Supporter).where(Supporter.full_name == "Wanjiku Njeri"))


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


async def test_a_mobilizer_row_cannot_attach_a_login_the_caller_cannot_see(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """Otherwise naming any user here makes them visible, and then removable."""
    from tests.factories import make_user

    victim = await make_user(session, username="victim", role=UserRole.MANAGER)
    await make_user(session, username="rival", role=UserRole.MANAGER)
    token = await sign_in(client, "rival")
    setup = await client.post(
        "/api/campaigns/setup/",
        headers=auth(token),
        json={
            "title": "Rival for Githurai",
            "office_level": "ward",
            "ward": str(world.other_ward.id),
            "new_candidate": {"username": "theirs"},
        },
    )
    assert setup.status_code == 201, setup.text
    mine = setup.json()["id"]

    hijack = await client.post(
        "/api/mobilizers/",
        headers=auth(token),
        json={
            "campaign": mine,
            "ward": str(world.other_ward.id),
            "user": str(victim.id),
            "full_name": "Not Really Them",
        },
    )

    assert hijack.status_code == 400
    assert "not a mobilizer" in hijack.json()["detail"]
    team = (await client.get("/api/users/", headers=auth(token))).json()
    assert "victim" not in [u["username"] for u in team]
    assert (await client.delete(f"/api/users/{victim.id}/", headers=auth(token))).status_code == 404


async def test_a_mobilizer_row_cannot_name_somebody_who_is_not_a_mobilizer(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post(
        "/api/mobilizers/",
        headers=world.headers("manager"),
        json={
            "campaign": str(world.campaign.id),
            "ward": str(world.ward.id),
            "user": str(world.candidate.id),
            "full_name": "Jane Again",
        },
    )

    assert response.status_code == 400
    assert "not a mobilizer" in response.json()["detail"]


async def test_an_unattached_mobilizer_login_can_be_put_on_the_ground(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """The `user` field has to still work; tightening it to nothing is not a fix."""
    from tests.factories import make_user

    spare = await make_user(session, username="spare", role=UserRole.MOBILIZER)

    response = await client.post(
        "/api/mobilizers/",
        headers=world.headers("manager"),
        json={
            "campaign": str(world.campaign.id),
            "ward": str(world.other_ward.id),
            "user": str(spare.id),
            "full_name": "Spare Organizer",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["user"] == str(spare.id)

    # Being on the ground is no use without being on the campaign: reads are
    # scoped by membership, so without one they sign in to an empty app.
    token = await sign_in(client, "spare")
    seen = await client.get("/api/campaigns/", headers=auth(token))
    assert [c["id"] for c in seen.json()] == [str(world.campaign.id)]


async def test_a_login_already_on_the_ground_is_refused_not_a_500(
    client: httpx.AsyncClient, world: World
) -> None:
    """Mobilizer.user_id is unique, so a second row would be an integrity error."""
    response = await client.post(
        "/api/mobilizers/",
        headers=world.headers("manager"),
        json={
            "campaign": str(world.campaign.id),
            "ward": str(world.other_ward.id),
            "user": str(world.mobilizer_user.id),
            "full_name": "Juma Again",
        },
    )

    assert response.status_code == 409
    assert "already on the ground" in response.json()["detail"]


async def test_an_event_cannot_name_another_campaign_s_mobilizer(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    from tests.factories import make_user

    await make_user(session, username="rival", role=UserRole.MANAGER)
    token = await sign_in(client, "rival")
    setup = await client.post(
        "/api/campaigns/setup/",
        headers=auth(token),
        json={
            "title": "Rival for Githurai",
            "office_level": "ward",
            "ward": str(world.other_ward.id),
            "new_candidate": {"username": "theirs"},
        },
    )
    assert setup.status_code == 201, setup.text

    response = await client.post(
        "/api/events/",
        headers=auth(token),
        json={
            "campaign": setup.json()["id"],
            "ward": str(world.other_ward.id),
            "mobilizer": str(world.mobilizer.id),
            "title": "Borrowed Organizer",
        },
    )

    assert response.status_code == 400
    assert "No such mobilizer on this campaign." in response.json()["detail"]


async def test_a_signed_out_write_cannot_reach_a_campaign_nobody_is_on(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """A campaign with no members is the superuser's to repair, not the internet's."""
    await session.execute(
        delete(CampaignMember).where(CampaignMember.campaign_id == world.campaign.id)
    )
    await session.commit()

    response = await client.post(
        "/api/supporters/",
        json={
            "campaign": str(world.campaign.id),
            "full_name": "Walk In",
            "consent_given": True,
        },
    )

    assert response.status_code == 401
    assert not await session.scalar(select(Supporter).where(Supporter.full_name == "Walk In"))


async def test_a_rival_campaign_cannot_write_into_this_register_with_its_id(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await make_user(session, username="rival", role=UserRole.MANAGER)
    await session.commit()
    token = await sign_in(client, "rival")

    response = await client.post(
        "/api/supporters/",
        headers=auth(token),
        json={
            "campaign": str(world.campaign.id),
            "full_name": "Planted",
            "consent_given": True,
        },
    )

    assert response.status_code == 404
    assert not await session.scalar(select(Supporter).where(Supporter.full_name == "Planted"))


async def test_a_mobilizer_login_from_another_campaign_cannot_be_planted_here(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """Their ward scoping lives on their own campaign; a second row would break it."""
    from backend.api.scope import add_member
    from backend.models import Campaign, OfficeLevel

    outsider = await make_user(session, username="theirs", role=UserRole.MOBILIZER)
    owner = await make_user(session, username="rival_boss", role=UserRole.CANDIDATE)
    await session.flush()
    theirs = Campaign(
        title="Rival for Githurai",
        office_level=OfficeLevel.WARD,
        ward_id=world.other_ward.id,
    )
    session.add(theirs)
    await session.flush()
    await add_member(session, theirs.id, owner.id)
    await add_member(session, theirs.id, outsider.id)
    await session.commit()

    refused = await client.post(
        "/api/mobilizers/",
        headers=world.headers("manager"),
        json={
            "campaign": str(world.campaign.id),
            "ward": str(world.ward.id),
            "user": str(outsider.id),
            "full_name": "Planted Organizer",
            "phone": "+254700999888",
        },
    )

    assert refused.status_code == 400
    assert not await session.scalar(
        select(Mobilizer).where(Mobilizer.full_name == "Planted Organizer")
    )


async def test_taking_a_mobilizer_off_the_ground_takes_the_campaign_with_it(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """Their ward went with the row, so the campaign would read as empty."""
    token = await sign_in(client, "juma")
    assert (await client.get("/api/campaigns/", headers=auth(token))).json() != []

    gone = await client.delete(
        f"/api/mobilizers/{world.mobilizer.id}/", headers=world.headers("manager")
    )

    assert gone.status_code == 204
    again = await sign_in(client, "juma")
    assert (await client.get("/api/campaigns/", headers=auth(again))).json() == []


async def test_taking_a_ground_row_off_does_not_take_the_candidate_off_their_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """A legacy ground row can belong to a candidate or a manager.

    The route that wrote `mobilizers.user_id` never checked the role, so the
    backfill puts such a person on as what their login says. Deleting the ground
    row must take the ward away, not the campaign.
    """
    session.add(
        Mobilizer(
            campaign_id=world.campaign.id,
            ward_id=world.ward.id,
            user_id=world.candidate.id,
            full_name="Jane On The Ground",
            phone="+254700555666",
        )
    )
    await session.commit()
    theirs = await session.scalar(select(Mobilizer).where(Mobilizer.user_id == world.candidate.id))

    gone = await client.delete(f"/api/mobilizers/{theirs.id}/", headers=world.headers("manager"))

    assert gone.status_code == 204
    still_on = await session.scalar(
        select(CampaignMember).where(
            CampaignMember.campaign_id == world.campaign.id,
            CampaignMember.user_id == world.candidate.id,
        )
    )
    assert still_on is not None, "the candidate was taken off their own campaign"
    token = await sign_in(client, "jane")
    assert [c["id"] for c in (await client.get("/api/campaigns/", headers=auth(token))).json()] == [
        str(world.campaign.id)
    ]
