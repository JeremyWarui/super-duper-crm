"""The public sign-up behind an event's QR code, and how it counts toward the ward's target."""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Event, EventStatus
from tests.conftest import World


async def _event(session: AsyncSession, world: World) -> Event:
    event = Event(
        campaign_id=world.campaign.id,
        ward_id=world.ward.id,
        mobilizer_id=world.mobilizer.id,
        title="Zimmerman town hall",
        status=EventStatus.DONE,
    )
    session.add(event)
    await session.commit()
    return event


def _person(**overrides) -> dict:
    return {
        "full_name": "Wanjiku Njeri",
        "phone": "0712 345678",
        "consent_given": True,
        **overrides,
    }


async def test_a_qr_sign_up_counts_once_toward_its_ward_and_credits_the_event(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    event = await _event(session, world)

    page = await client.get(f"/api/join/{event.signup_code}/")
    first = await client.post(f"/api/join/{event.signup_code}/", json=_person())
    again = await client.post(
        f"/api/join/{event.signup_code}/", json=_person(phone="+254712345678")
    )
    register = (await client.get("/api/supporters/", headers=world.headers("manager"))).json()
    events = (await client.get("/api/events/", headers=world.headers("manager"))).json()
    units = (await client.get("/api/strategy/", headers=world.headers("manager"))).json()["units"]

    assert (page.json()["event_title"], page.json()["open"]) == ("Zimmerman town hall", True)
    assert (first.status_code, again.status_code) == (201, 201)
    assert [(s["phone"], s["mobilizer"], s["ward"]) for s in register] == [
        ("+254712345678", str(world.mobilizer.id), str(world.ward.id))
    ]
    assert [e["signups"] for e in events] == [1]
    assert {u["unit"]: u["committed"] for u in units}["Zimmerman"] == 1


async def test_a_closed_or_unconsented_sign_up_is_refused(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    event = await _event(session, world)

    no_consent = await client.post(
        f"/api/join/{event.signup_code}/", json=_person(consent_given=False)
    )
    await client.post(
        f"/api/events/{event.id}/signups/", headers=world.headers("manager"), json={"open": False}
    )
    closed = await client.post(f"/api/join/{event.signup_code}/", json=_person())

    assert (no_consent.status_code, closed.status_code) == (400, 400)


async def test_the_candidate_does_not_get_the_sign_up_code(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    event = await _event(session, world)

    manager = (await client.get("/api/events/", headers=world.headers("manager"))).json()
    candidate = (await client.get("/api/events/", headers=world.headers("candidate"))).json()

    assert [e["signup_code"] for e in manager] == [event.signup_code]
    assert [e["signup_code"] for e in candidate] == [None]


async def test_one_phone_in_other_digit_scripts_is_still_one_person(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    event = await _event(session, world)
    url = f"/api/join/{event.signup_code}/"

    await client.post(url, json=_person())
    for spelled in ("٧١٢٣٤٥٦٧٨", "７１２３４５６７８", "७१२३४५६७८", "71２345678"):
        await client.post(url, json=_person(full_name="Someone Else", phone=spelled))
    register = (await client.get("/api/supporters/", headers=world.headers("manager"))).json()

    assert [(s["full_name"], s["phone"]) for s in register] == [("Wanjiku Njeri", "+254712345678")]


async def test_an_mca_sign_up_counts_toward_its_event_s_centre(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    from backend.services.strategy import read_strategy
    from backend.services.targets import generate_targets
    from tests.factories import make_campaign

    mca = await make_campaign(session, world.ward)
    await generate_targets(session, mca)
    event = Event(
        campaign_id=mca.id,
        ward_id=world.ward.id,
        registration_centre_id=world.centre.id,
        title="Zimmerman Primary meeting",
    )
    session.add(event)
    await session.commit()

    await client.post(f"/api/join/{event.signup_code}/", json=_person())
    units = (await read_strategy(session, campaign_ids=frozenset({mca.id}))).units

    assert mca.seat.value == "mca"
    assert [(u.unit, u.committed) for u in units] == [("Zimmerman Primary", 1)]
