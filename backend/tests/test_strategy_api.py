"""The computed strategy read: the totals, the per-unit rows, and the flags."""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Event, EventStatus, Mobilizer, Target
from tests.conftest import World


async def _strategy(client: httpx.AsyncClient, world: World, role: str = "manager") -> dict:
    response = await client.get(
        f"/api/strategy/?campaign={world.campaign.id}", headers=world.headers(role)
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _commit(session: AsyncSession, ward_name: str, votes: int) -> Target:
    target = next(
        t
        for t in (await session.execute(select(Target))).scalars().all()
        if t.ward.name == ward_name
    )
    target.votes_committed = votes
    await session.commit()
    return target


async def test_the_strategy_read_needs_a_token(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/strategy/")).status_code == 401


async def test_the_win_number_is_the_sum_across_every_unit(
    client: httpx.AsyncClient, world: World
) -> None:
    """Zimmerman 9,211 plus Githurai 10,770."""
    body = await _strategy(client, world)

    assert body["win_number"] == 19_981
    assert body["total_registered"] == 66_600
    assert len(body["units"]) == 2


async def test_the_projected_votes_cast_are_the_register_at_the_projected_turnout(
    client: httpx.AsyncClient, world: World
) -> None:
    """66,600 on the roll at 60% is 39,960 cast."""
    body = await _strategy(client, world)
    assert body["total_cast"] == 39_960


async def test_progress_is_committed_over_the_win_number(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await _commit(session, "Zimmerman", 9_211)

    body = await _strategy(client, world)

    assert body["committed"] == 9_211
    assert body["progress_pct"] == 46.1


async def test_each_unit_carries_its_gap_and_its_share_of_the_win_number(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await _commit(session, "Zimmerman", 4_606)

    body = await _strategy(client, world)
    zimmerman = next(u for u in body["units"] if u["unit"] == "Zimmerman")

    assert zimmerman["needed"] == 9_211
    assert zimmerman["committed"] == 4_606
    assert zimmerman["gap"] == 4_605
    assert zimmerman["progress"] == 0.5
    assert zimmerman["share"] == 0.461


async def test_a_unit_past_its_goal_reports_no_gap(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await _commit(session, "Zimmerman", 20_000)

    zimmerman = next(
        u for u in (await _strategy(client, world))["units"] if u["unit"] == "Zimmerman"
    )

    assert zimmerman["gap"] == 0
    assert zimmerman["progress"] > 1


async def test_a_unit_counts_its_events_and_whether_anyone_is_working_it(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    session.add_all(
        [
            Event(campaign_id=world.campaign.id, ward_id=world.ward.id, title="One"),
            Event(campaign_id=world.campaign.id, ward_id=world.ward.id, title="Two"),
        ]
    )
    await session.commit()

    body = await _strategy(client, world)
    zimmerman = next(u for u in body["units"] if u["unit"] == "Zimmerman")
    githurai = next(u for u in body["units"] if u["unit"] == "Githurai")

    assert zimmerman["events"] == 2
    assert zimmerman["has_mobilizer"] is True
    assert githurai["events"] == 0
    assert githurai["has_mobilizer"] is False


async def test_a_centre_s_events_do_not_count_towards_the_ward_around_it(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    session.add(
        Event(
            campaign_id=world.campaign.id,
            ward_id=world.ward.id,
            registration_centre_id=world.centre.id,
            title="Centre meeting",
        )
    )
    await session.commit()

    zimmerman = next(
        u for u in (await _strategy(client, world))["units"] if u["unit"] == "Zimmerman"
    )

    assert zimmerman["events"] == 0


async def test_the_first_note_points_at_the_biggest_gap(
    client: httpx.AsyncClient, world: World
) -> None:
    body = await _strategy(client, world)

    go = body["notes"][0]
    assert go["tone"] == "go"
    assert go["title"] == "Go next: Githurai"
    assert "10,770 votes short" in go["text"]
    assert "54% of the win number is here" in go["text"]


async def test_the_go_note_says_what_is_missing_there(
    client: httpx.AsyncClient, world: World
) -> None:
    go = (await _strategy(client, world))["notes"][0]

    assert "no events yet" in go["text"]
    assert "no mobilizer" in go["text"]


async def test_a_single_event_reads_as_only_one_rather_than_none(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    session.add(
        Event(campaign_id=world.campaign.id, ward_id=world.other_ward.id, title="Githurai rally")
    )
    await session.commit()

    go = (await _strategy(client, world))["notes"][0]

    assert "only 1 event" in go["text"]
    assert "no events yet" not in go["text"]


async def test_unstaffed_units_are_flagged_by_name(client: httpx.AsyncClient, world: World) -> None:
    notes = (await _strategy(client, world))["notes"]

    unstaffed = next(n for n in notes if "unstaffed" in n["title"])
    assert unstaffed["title"] == "1 unit unstaffed"
    assert "Githurai" in unstaffed["text"]


async def test_a_well_worked_unit_that_has_met_its_goal_says_to_ease_off(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await _commit(session, "Zimmerman", 10_000)
    session.add_all(
        [
            Event(campaign_id=world.campaign.id, ward_id=world.ward.id, title=f"Rally {n}")
            for n in range(4)
        ]
    )
    await session.commit()

    notes = (await _strategy(client, world))["notes"]

    assert any(n["title"] == "Ease off: Zimmerman" for n in notes)


async def test_a_unit_that_met_its_goal_without_much_work_is_not_flagged(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await _commit(session, "Zimmerman", 10_000)
    session.add(Event(campaign_id=world.campaign.id, ward_id=world.ward.id, title="Rally"))
    await session.commit()

    notes = (await _strategy(client, world))["notes"]

    assert not any("Ease off" in n["title"] for n in notes)


async def test_a_fully_staffed_campaign_raises_no_staffing_flag(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    session.add(
        Mobilizer(
            campaign_id=world.campaign.id, ward_id=world.other_ward.id, full_name="Wanjiku Njeri"
        )
    )
    await session.commit()

    notes = (await _strategy(client, world))["notes"]

    assert not any("unstaffed" in n["title"] for n in notes)


async def test_a_campaign_with_nothing_in_it_reads_as_zero_rather_than_failing(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    for target in (await session.execute(select(Target))).scalars().all():
        await session.delete(target)
    await session.commit()

    body = await _strategy(client, world)

    assert body == {
        "win_number": 0,
        "committed": 0,
        "progress_pct": 0.0,
        "total_registered": 0,
        "total_cast": 0,
        "units": [],
        "notes": [],
    }


# ------------------------------------------------------------ what each role sees


async def test_a_candidate_reads_the_same_strategy_as_the_manager(
    client: httpx.AsyncClient, world: World
) -> None:
    assert await _strategy(client, world, "candidate") == await _strategy(client, world, "manager")


async def test_a_mobilizer_sees_only_their_own_ward_in_the_strategy(
    client: httpx.AsyncClient, world: World
) -> None:
    body = await _strategy(client, world, "mobilizer")

    assert [u["unit"] for u in body["units"]] == ["Zimmerman"]
    assert body["win_number"] == 9_211


async def test_a_done_event_still_counts_towards_its_unit(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    session.add(
        Event(
            campaign_id=world.campaign.id,
            ward_id=world.ward.id,
            title="Held already",
            status=EventStatus.DONE,
            number_reached=200,
            number_attended=150,
        )
    )
    await session.commit()

    zimmerman = next(
        u for u in (await _strategy(client, world))["units"] if u["unit"] == "Zimmerman"
    )

    assert zimmerman["events"] == 1
