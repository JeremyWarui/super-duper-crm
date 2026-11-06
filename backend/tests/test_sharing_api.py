"""A hosted campaign shares counts with the party only while its candidate has a switch on, and
never a supporter's row or phone."""

from datetime import date

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    County,
    OfficeLevel,
    PartyPost,
    PartyRoleName,
    PostKind,
    Supporter,
    WorkspaceKind,
)
from tests.conftest import World
from tests.factories import auth, make_officer, sign_in

pytestmark = pytest.mark.party_only

ALL_ON = {"event_reach": True, "ward_coverage": True, "supporter_counts": True}
ALL_OFF = dict.fromkeys(ALL_ON, False)


def _sharing(world: World) -> str:
    return f"/api/party-feed/sharing/?campaign={world.campaign.id}"


async def _shared(client: httpx.AsyncClient, admin: dict, world: World) -> dict:
    rows = (await client.get("/api/party/shared/", headers=admin)).json()
    return next(r for r in rows if r["id"] == str(world.campaign.id))


async def test_nothing_is_shared_until_the_candidate_switches_it_on_and_off_hides_it_at_once(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    session.add(Supporter(campaign_id=world.campaign.id, ward_id=world.ward.id, full_name="A"))
    await session.commit()

    before = await _shared(client, admin_headers, world)
    by_manager = await client.put(_sharing(world), json=ALL_ON, headers=world.headers("manager"))
    on = await client.put(_sharing(world), json=ALL_ON, headers=world.headers("candidate"))
    during = await _shared(client, admin_headers, world)
    await client.put(_sharing(world), json=ALL_OFF, headers=world.headers("candidate"))
    after = await _shared(client, admin_headers, world)
    page = await client.get(
        f"/api/party-feed/?campaign={world.campaign.id}", headers=world.headers("manager")
    )

    assert [before[k] for k in ALL_ON] == [None, None, None]
    assert by_manager.status_code == 403
    assert on.json() == ALL_ON
    assert during["supporter_counts"] == [
        {"ward_id": str(world.ward.id), "ward": "Zimmerman", "count": 1}
    ]
    assert (during["ward_coverage"]["wards"], len(during["ward_coverage"]["covered"])) == (2, 1)
    assert during["event_reach"] == {"events": 0, "reached": 0, "attended": 0}
    assert [after[k] for k in ALL_ON] == [None, None, None]
    assert len(page.json()["history"]) == 6
    assert page.json()["can_change"] is False


async def test_no_route_gives_a_party_login_a_supporter_row_or_phone(
    client: httpx.AsyncClient, session: AsyncSession, world: World, admin_headers: dict
) -> None:
    session.add(
        Supporter(
            campaign_id=world.campaign.id,
            ward_id=world.ward.id,
            full_name="Wanjiru Siri",
            phone="+254712000999",
        )
    )
    await session.commit()
    await make_officer(session, world.ward, PartyRoleName.MEMBERSHIP_OFFICER, username="ofisa")
    officer = auth(await sign_in(client, "ofisa"))
    await client.put(_sharing(world), json=ALL_ON, headers=world.headers("candidate"))

    shared = await client.get("/api/party/shared/", headers=admin_headers)
    register = await client.get(f"/api/supporters/?campaign={world.campaign.id}", headers=officer)
    feed = await client.get(f"/api/party-feed/?campaign={world.campaign.id}", headers=officer)

    assert shared.status_code == 200
    assert "Wanjiru" not in shared.text and "712000999" not in shared.text
    assert register.status_code in (403, 404)
    assert feed.status_code in (403, 404)


@pytest.mark.parametrize("kind", [WorkspaceKind.PARTY, WorkspaceKind.STANDALONE])
async def test_party_and_standalone_workspaces_have_no_sharing_page(
    client: httpx.AsyncClient, session: AsyncSession, world: World, kind: WorkspaceKind
) -> None:
    world.campaign.kind = kind
    if kind is WorkspaceKind.PARTY:
        world.campaign.seat, world.campaign.constituency_id = None, None
        world.campaign.office_level = OfficeLevel.NATIONAL
    await session.commit()

    page = await client.get(
        f"/api/party-feed/?campaign={world.campaign.id}", headers=world.headers("manager")
    )
    change = await client.put(_sharing(world), json=ALL_ON, headers=world.headers("candidate"))

    assert (page.status_code, change.status_code) == (404, 404)


async def test_the_feed_shows_party_events_in_the_area_and_member_counts_per_ward(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    other = County(name="Mombasa", code="001")
    session.add_all(
        [
            other,
            PartyPost(
                kind=PostKind.EVENT,
                title="Rally here",
                event_date=date(2026, 11, 20),
                county_id=world.county.id,
                published=True,
            ),
            PartyPost(
                kind=PostKind.EVENT,
                title="Rally there",
                event_date=date(2026, 11, 20),
                county=other,
                published=True,
            ),
        ]
    )
    await session.commit()
    await make_officer(session, world.ward, username="mwanachama")

    feed = (
        await client.get(
            f"/api/party-feed/?campaign={world.campaign.id}", headers=world.headers("manager")
        )
    ).json()

    assert [e["title"] for e in feed["events"]] == ["Rally here"]
    assert {w["ward"]: w["count"] for w in feed["members_by_ward"]} == {
        "Githurai": 0,
        "Zimmerman": 1,
    }


async def test_a_first_save_with_every_share_off_is_kept(
    client: httpx.AsyncClient, world: World
) -> None:
    saved = await client.put(_sharing(world), json=ALL_OFF, headers=world.headers("candidate"))

    assert (saved.status_code, saved.json()) == (200, ALL_OFF)
