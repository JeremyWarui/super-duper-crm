"""Trying and setting the turnout scenario the team works to (TD-R7 section 6.1).

Trying a scenario works the targets out on the server and saves nothing. Setting one saves every
target, records an audit entry and tells each coordinator and mobilizer whose target changed.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    Campaign,
    CampaignMember,
    CampaignMemberArea,
    Constituency,
    Mobilizer,
    Notice,
    Target,
    TurnoutScenario,
    User,
    UserRole,
    Ward,
)
from backend.services import push
from backend.services.audit import record
from backend.services.errors import Refused
from backend.services.targets import generate_targets, plan_targets
from backend.services.win_model import as_decimal

# Where each notice opens: a page that shows the recipient's set target.
COORDINATOR_PAGE = "/campaign/overview"
MOBILIZER_PAGE = "/campaign/myevents"


def _pct(value) -> str:  # type: ignore[no-untyped-def]
    return str(as_decimal(value * 100, 2))


async def _saved(session: AsyncSession, campaign_id: uuid.UUID) -> dict[tuple, Target]:
    rows = await session.scalars(
        select(Target)
        .where(Target.campaign_id == campaign_id)
        .options(selectinload(Target.ward), selectinload(Target.registration_centre))
    )
    return {(t.ward_id, t.registration_centre_id): t for t in rows}


async def preview(
    session: AsyncSession,
    campaign: Campaign,
    scenario: TurnoutScenario,
    *,
    county: uuid.UUID | None = None,
) -> dict:
    """The seat and each unit's target under this scenario beside what is set; saves nothing.
    A national seat lists one county's wards at a time."""
    plan = await plan_targets(session, campaign, scenario)
    saved = await _saved(session, campaign.id)
    model, history = plan.model, plan.history
    latest = history.results.get(2022)
    set_target = sum(t.votes_needed or 0 for t in saved.values())
    units = []
    changed = 0
    for ward, centre in plan.units:
        key = (ward.id, centre.id if centre is not None else None)
        current = saved.get(key)
        if current is not None and current.votes_needed != plan.shares[key]:
            changed += 1
        if (county is not None and ward.constituency.county_id != county) or (
            county is None and campaign.national
        ):
            continue
        units.append(
            {
                "ward": ward.id,
                "registration_centre": key[1],
                "name": centre.name if centre is not None else ward.name,
                "weight_pct": _pct(plan.weight(key)),
                "target": plan.shares[key],
                "set_target": current.votes_needed if current is not None else None,
                "supporters": current.votes_committed if current is not None else 0,
            }
        )
    units.sort(key=lambda u: u["target"], reverse=True)
    return {
        "scenario": scenario,
        "set_scenario": campaign.turnout_scenario,
        "set_by": campaign.turnout_scenario_set_by_id,
        "set_at": campaign.turnout_scenario_set_at,
        "seat": campaign.seat.label,
        "registered_voters": history.register,
        "winner_votes": max(latest.votes) if latest is not None and latest.votes else None,
        "valid_votes": latest.valid if latest is not None else None,
        "share_pct": _pct(model.share),
        "typical_pct": _pct(model.typical) if model.typical is not None else None,
        "reliability": model.reliability,
        "two_candidate": model.two_candidate,
        "uses_2017": model.uses_2017,
        "scenarios": [
            {
                "scenario": p.scenario,
                "turnout_pct": _pct(p.turnout),
                "projected": p.projected,
                "majority": p.majority,
                "target": p.target,
            }
            for p in model.scenarios.values()
        ],
        "seat_target": plan.seat_target,
        "set_seat_target": set_target,
        "majority": plan.projection.majority,
        "supporters": sum(t.votes_committed for t in saved.values()),
        "units_changed": changed,
        "units": units,
    }


async def _affected(
    session: AsyncSession, campaign_id: uuid.UUID, changed: list[Target]
) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    """The coordinators whose area holds a changed unit, and the mobilizers on one."""
    if not changed:
        return [], []
    wards = {t.ward_id for t in changed}
    centres = {t.registration_centre_id for t in changed if t.registration_centre_id}
    found = await session.execute(
        select(Ward.id, Constituency.id, Constituency.county_id)
        .join(Constituency, Constituency.id == Ward.constituency_id)
        .where(Ward.id.in_(wards))
    )
    constituencies, counties = set(), set()
    for _, constituency, county in found:
        constituencies.add(constituency)
        counties.add(county)
    coordinators = (
        select(CampaignMember.user_id)
        .join(CampaignMemberArea, CampaignMemberArea.campaign_member_id == CampaignMember.id)
        .where(
            CampaignMember.campaign_id == campaign_id,
            CampaignMember.role == UserRole.COORDINATOR,
            or_(
                CampaignMemberArea.ward_id.in_(wards),
                CampaignMemberArea.registration_centre_id.in_(centres or {uuid.UUID(int=0)}),
                CampaignMemberArea.constituency_id.in_(constituencies),
                CampaignMemberArea.county_id.in_(counties),
            ),
        )
    )
    on_unit = or_(
        Mobilizer.registration_centre_id.in_(centres or {uuid.UUID(int=0)}),
        Mobilizer.ward_id.in_(wards) & Mobilizer.registration_centre_id.is_(None),
    )
    mobilizers = select(Mobilizer.user_id).where(
        Mobilizer.campaign_id == campaign_id, Mobilizer.user_id.is_not(None), on_unit
    )
    return (
        list(dict.fromkeys(await session.scalars(coordinators))),
        list(dict.fromkeys(await session.scalars(mobilizers))),
    )


async def set_scenario(
    session: AsyncSession, campaign: Campaign, scenario: TurnoutScenario, *, actor: User
) -> dict:
    """Make this the scenario the team works to: every target is worked out again and saved, the
    change is audited, and everyone whose target changed is told. Commits."""
    old_scenario = campaign.turnout_scenario
    if scenario == old_scenario:
        raise Refused(f"The team already works to the {scenario.label} scenario.")
    # Waits for any other setting in flight, and refuses if it changed the scenario meanwhile.
    moved = await session.execute(
        update(Campaign)
        .where(Campaign.id == campaign.id, Campaign.turnout_scenario == old_scenario)
        .values(
            turnout_scenario=scenario,
            turnout_scenario_set_by_id=actor.id,
            turnout_scenario_set_at=datetime.now(UTC),
        )
        .execution_options(synchronize_session=False)
    )
    if moved.rowcount == 0:
        await session.rollback()
        raise Refused("Someone else changed the scenario just now; look again before setting it.")
    before = {key: t.votes_needed for key, t in (await _saved(session, campaign.id)).items()}
    old_target = sum(v or 0 for v in before.values())
    await session.refresh(campaign)
    summary = await generate_targets(session, campaign)
    after = await _saved(session, campaign.id)
    changed = [t for key, t in after.items() if before.get(key) != t.votes_needed]

    record(
        session,
        actor=actor,
        action="targets.set_scenario",
        subject_type="campaign",
        subject_id=campaign.id,
        campaign_id=campaign.id,
        detail={
            "from": old_scenario.value,
            "to": scenario.value,
            "seat_target_from": old_target,
            "seat_target_to": summary.win_number,
            "units_changed": len(changed),
        },
    )
    coordinators, mobilizers = await _affected(session, campaign.id, changed)
    text = (
        f"Targets changed: the team now works to {scenario.label} turnout. "
        f"The seat target is {summary.win_number:,}."
    )
    pages = [(user_id, COORDINATOR_PAGE) for user_id in coordinators]
    pages += [(user_id, MOBILIZER_PAGE) for user_id in mobilizers if user_id not in coordinators]
    session.add_all(
        Notice(campaign_id=campaign.id, user_id=user_id, text=text, url=url)
        for user_id, url in pages
    )
    await session.commit()
    for url in (COORDINATOR_PAGE, MOBILIZER_PAGE):
        await push.notify(
            session, [u for u, at in pages if at == url], "Targets changed", text, url
        )
    told = pages
    return {
        "scenario": scenario,
        "seat_target_from": old_target,
        "seat_target_to": summary.win_number,
        "units_changed": len(changed),
        "notified": len(told),
    }
