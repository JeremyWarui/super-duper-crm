"""The public sign-up behind an event's QR code, and how it counts toward the ward's target."""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Event, EventStatus, Supporter
from tests.conftest import World
from tests.factories import make_geography


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


async def test_a_qr_sign_up_stores_the_wording_the_page_served_and_its_channel(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    event = await _event(session, world)

    served = (await client.get(f"/api/join/{event.signup_code}/")).json()["consent_wording"]
    await client.post(f"/api/join/{event.signup_code}/", json=_person())
    stored = (await session.scalars(select(Supporter))).one()

    assert (stored.consent_channel, stored.consent_wording) == ("event_qr", served)
    assert served


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


async def _open_campaign_link(client: httpx.AsyncClient, world: World) -> str:
    url = f"/api/campaigns/{world.campaign.id}/signups/"
    await client.post(url, headers=world.headers("manager"), json={"open": True})
    return (await client.get(url, headers=world.headers("manager"))).json()["code"]


async def test_only_the_manager_reads_or_opens_the_campaign_link(
    client: httpx.AsyncClient, world: World
) -> None:
    url = f"/api/campaigns/{world.campaign.id}/signups/"
    before = (await client.get(url, headers=world.headers("manager"))).json()

    refused = [
        (await client.get(url, headers=world.headers(role))).status_code
        for role in ("candidate", "mobilizer")
    ] + [
        (await client.post(url, headers=world.headers(role), json={"open": True})).status_code
        for role in ("candidate", "mobilizer")
    ]

    assert before["open"] is False
    assert refused == [403, 403, 403, 403]
    closed = await client.post(f"/api/join/{before['code']}/", json=_person())
    assert (closed.status_code, closed.json()["detail"]) == (400, "Sign-ups are closed.")


async def test_the_campaign_link_files_a_person_at_the_ward_they_pick_from_the_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    code = await _open_campaign_link(client, world)
    elsewhere = (await make_geography(session))[2]

    page = (await client.get(f"/api/join/{code}/")).json()
    no_ward = await client.post(f"/api/join/{code}/", json=_person())
    off_campaign = await client.post(f"/api/join/{code}/", json=_person(place=str(elsewhere.id)))
    joined = await client.post(f"/api/join/{code}/", json=_person(place=str(world.other_ward.id)))
    register = (await client.get("/api/supporters/", headers=world.headers("manager"))).json()

    assert (page["place"], [p["name"] for p in page["places"]]) == (
        "ward",
        ["Githurai", "Zimmerman"],
    )
    assert [no_ward.status_code, off_campaign.status_code, joined.status_code] == [400, 400, 201]
    assert [s["ward"] for s in register] == [str(world.other_ward.id)]


async def test_an_mca_person_unsure_of_their_centre_waits_to_be_placed(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    from backend.services.strategy import read_strategy
    from backend.services.targets import generate_targets
    from tests.factories import make_campaign

    mca = await make_campaign(session, world.ward)
    await generate_targets(session, mca)
    mca.signups_open = True
    await session.commit()

    page = (await client.get(f"/api/join/{mca.signup_code}/")).json()
    joined = await client.post(f"/api/join/{mca.signup_code}/", json=_person())
    strategy = await read_strategy(session, campaign_ids=frozenset({mca.id}))

    assert (page["place"], [p["name"] for p in page["places"]]) == ("centre", ["Zimmerman Primary"])
    assert joined.status_code == 201
    assert [n.title for n in strategy.notes][0] == "1 supporter needs a centre"


async def test_a_person_withdraws_with_their_own_link_and_no_link_tells_anything(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    event = await _event(session, world)
    url = f"/api/join/{event.signup_code}/"
    first = (await client.post(url, json=_person())).json()
    repeat = (await client.post(url, json=_person(full_name="Someone Else"))).json()

    answers = [
        (r.status_code, r.json())
        for r in [
            await client.post(f"/api/join/withdraw/{repeat['withdraw_code']}/"),
            await client.post("/api/join/withdraw/made-up-code/"),
        ]
    ]
    still_there = await session.scalar(
        select(Supporter.full_name).where(Supporter.phone == "+254712345678")
    )
    gone = await client.post(f"/api/join/withdraw/{first['withdraw_code']}/")
    used_again = await client.post(f"/api/join/withdraw/{first['withdraw_code']}/")
    register = (await client.get("/api/supporters/", headers=world.headers("manager"))).json()

    assert first["withdraw_code"] != repeat["withdraw_code"]
    assert still_there == "Wanjiku Njeri"
    assert answers == [(gone.status_code, gone.json())] * 2
    assert (used_again.status_code, used_again.json()) == (gone.status_code, gone.json())
    assert register == []


async def test_withdrawal_tries_are_limited_like_sign_ups(client: httpx.AsyncClient) -> None:
    answers = [(await client.post(f"/api/join/withdraw/guess-{n}/")).status_code for n in range(21)]

    assert answers == [200] * 20 + [429]


async def test_another_campaign_s_manager_cannot_read_or_open_the_link(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    from backend.models import UserRole
    from backend.services.accounts import add_member
    from tests.factories import auth, make_rival_campaign, make_user, sign_in

    rival = await make_rival_campaign(session, world.other_ward)
    other = await make_user(session, username="othermanager", role=UserRole.MANAGER)
    await add_member(session, rival.id, other)
    await session.commit()
    head = auth(await sign_in(client, "othermanager"))
    url = f"/api/campaigns/{world.campaign.id}/signups/"

    read = await client.get(url, headers=head)
    opened = await client.post(url, headers=head, json={"open": True})

    assert (read.status_code, opened.status_code) == (404, 404)
    assert world.campaign.signups_open is False
