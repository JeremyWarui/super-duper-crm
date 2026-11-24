"""Trying and setting the team's turnout scenario on the Laikipia governor seat (TD-R7 R7-4)."""

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    AuditEvent,
    CampaignMemberArea,
    County,
    Notice,
    OfficeLevel,
    Seat,
    Target,
    User,
    UserRole,
    Ward,
)
from backend.models.campaign import Campaign
from backend.seed.history import RESULTS_CSV, import_results
from backend.seed.reference import import_geography
from backend.services.accounts import add_member
from backend.services.targets import generate_targets
from tests.factories import auth, make_mobilizer_user, make_user, sign_in

pytestmark = pytest.mark.skipif(not RESULTS_CSV.exists(), reason="the results file is not bundled")


async def laikipia(session: AsyncSession, client: httpx.AsyncClient) -> tuple[Campaign, dict]:
    await import_geography(session)
    await import_results(session)
    county = await session.scalar(select(County).where(County.code == "31"))
    campaign = Campaign(
        title="Governor", office_level=OfficeLevel.COUNTY, seat=Seat.GOVERNOR, county_id=county.id
    )
    session.add(campaign)
    await session.flush()
    await generate_targets(session, campaign)
    await session.commit()
    ward = {w.name: w for w in await session.scalars(select(Ward))}
    heads = {}
    for name, role in (("manager", UserRole.MANAGER), ("comms", UserRole.COMMS)):
        user = await make_user(session, username=name, role=role)
        await add_member(session, campaign.id, user)
        heads[name] = auth(await sign_in(client, name))
    coordinator = await make_user(session, username="coord", role=UserRole.COORDINATOR)
    member = await add_member(session, campaign.id, coordinator)
    session.add(CampaignMemberArea(campaign_member_id=member.id, ward_id=ward["Igwamiti"].id))
    await make_mobilizer_user(session, campaign, ward["Nanyuki"])
    await session.commit()
    heads["coordinator"] = auth(await sign_in(client, "coord"))
    heads["mobilizer"] = auth(await sign_in(client, "juma"))
    return campaign, heads


async def test_a_scenario_is_tried_without_saving_and_set_only_by_the_leads(
    session: AsyncSession, client: httpx.AsyncClient
) -> None:
    campaign, heads = await laikipia(session, client)
    base = f"/api/campaigns/{campaign.id}/targets"

    shown = await client.get(f"{base}/preview/", headers=heads["comms"])
    high = await client.get(f"{base}/preview/?scenario=high", headers=heads["comms"])
    after_preview = await client.get(f"{base}/preview/", headers=heads["manager"])
    mobilizer_tries = await client.get(f"{base}/preview/?scenario=high", headers=heads["mobilizer"])
    comms_sets = await client.post(
        f"{base}/scenario/", json={"scenario": "high"}, headers=heads["comms"]
    )
    mobilizer_sets = await client.post(
        f"{base}/scenario/", json={"scenario": "high"}, headers=heads["mobilizer"]
    )

    page = shown.json()
    assert (page["share_pct"], page["seat_target"], page["set_scenario"]) == (
        "67.86",
        113_783,
        "expected",
    )
    assert [s["target"] for s in page["scenarios"]] == [108_429, 113_783, 128_640]
    assert {u["name"]: u["target"] for u in page["units"]}["Igwamiti"] == 17_870
    assert (high.json()["seat_target"], high.json()["set_seat_target"]) == (128_640, 113_783)
    assert after_preview.json()["seat_target"] == 113_783
    assert [r.status_code for r in (mobilizer_tries, comms_sets, mobilizer_sets)] == [403] * 3


async def test_setting_high_saves_every_ward_audits_it_and_tells_the_affected_team(
    session: AsyncSession, client: httpx.AsyncClient
) -> None:
    campaign, heads = await laikipia(session, client)
    base = f"/api/campaigns/{campaign.id}/targets"

    answer = await client.post(
        f"{base}/scenario/", json={"scenario": "high"}, headers=heads["manager"]
    )
    again = await client.post(
        f"{base}/scenario/", json={"scenario": "high"}, headers=heads["manager"]
    )
    total = await session.scalar(
        select(func.sum(Target.votes_needed)).where(Target.campaign_id == campaign.id)
    )
    audit = await session.scalar(
        select(AuditEvent).where(AuditEvent.action == "targets.set_scenario")
    )
    mobilizer_notes = (await client.get("/api/notices/", headers=heads["mobilizer"])).json()
    comms_notes = (await client.get("/api/notices/", headers=heads["comms"])).json()

    assert answer.status_code == 200, answer.text
    assert answer.json() | {"notified": answer.json()["notified"]} == {
        "scenario": "high",
        "seat_target_from": 113_783,
        "seat_target_to": 128_640,
        "units_changed": 15,
        "notified": 2,
    }
    assert again.status_code == 400
    assert total == 128_640
    assert (audit.detail["from"], audit.detail["to"]) == ("expected", "high")
    coordinator_notes = (await client.get("/api/notices/", headers=heads["coordinator"])).json()
    assert [n["url"] for n in mobilizer_notes] == ["/campaign/myevents"]
    assert [n["url"] for n in coordinator_notes] == ["/campaign/overview"]
    assert comms_notes == []
    assert await session.scalar(select(func.count(Notice.id))) == 2


async def test_a_setting_that_lost_a_race_is_refused_and_changes_nothing(
    session: AsyncSession, client: httpx.AsyncClient
) -> None:
    from sqlalchemy import update

    from backend.models import Campaign as CampaignModel
    from backend.models import TurnoutScenario
    from backend.services.errors import Refused
    from backend.services.target_scenarios import set_scenario

    campaign, _ = await laikipia(session, client)
    manager = await session.scalar(select(User).where(User.username == "manager"))
    # Another request set Low after this one read the campaign at Expected.
    await session.execute(
        update(CampaignModel)
        .where(CampaignModel.id == campaign.id)
        .values(turnout_scenario=TurnoutScenario.LOW)
        .execution_options(synchronize_session=False)
    )
    await session.commit()

    with pytest.raises(Refused, match="Someone else changed the scenario"):
        await set_scenario(session, campaign, TurnoutScenario.HIGH, actor=manager)

    assert (
        await session.scalar(
            select(func.count(AuditEvent.id)).where(AuditEvent.action == "targets.set_scenario")
        )
        == 0
    )
