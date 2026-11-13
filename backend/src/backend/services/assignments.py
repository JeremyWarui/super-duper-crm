"""Work given to a workspace's mobilizers and agents, marked done before it is paid for."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.session import first_or_refuse, move_row
from backend.models import (
    Agent,
    Assignment,
    AssignmentKind,
    AssignmentStatus,
    Campaign,
    Event,
    EventStatus,
    Mobilizer,
    User,
)
from backend.services.accounts import campaign_mobilizer
from backend.services.audit import record
from backend.services.errors import Refused
from backend.services.permissions import Area, narrow
from backend.services.targets import require_centre, require_ward

WITH_DETAIL = (
    selectinload(Assignment.mobilizer),
    selectinload(Assignment.agent).selectinload(Agent.user),
    selectinload(Assignment.event),
    selectinload(Assignment.ward),
    selectinload(Assignment.registration_centre),
)


async def assignments(
    session: AsyncSession,
    campaign_id: uuid.UUID,
    area: Area | None,
    *,
    mobilizer_id: uuid.UUID | None = None,
    agent_id: uuid.UUID | None = None,
    status: AssignmentStatus | None = None,
) -> list[Assignment]:
    """A workspace's assignments inside `area`, or one member's own, newest first."""
    statement = select(Assignment).where(Assignment.campaign_id == campaign_id)
    if mobilizer_id or agent_id:
        statement = statement.where(
            Assignment.mobilizer_id == mobilizer_id
            if mobilizer_id
            else Assignment.agent_id == agent_id
        )
    else:
        statement = narrow(statement, area, Assignment)
    if status is not None:
        statement = statement.where(Assignment.status == status)
    found = await session.scalars(
        statement.options(*WITH_DETAIL).order_by(Assignment.created_at.desc())
    )
    return list(found)


async def assignment(
    session: AsyncSession, campaign_id: uuid.UUID, assignment_id: uuid.UUID, area: Area | None
) -> Assignment:
    return await first_or_refuse(
        session,
        narrow(
            select(Assignment).where(
                Assignment.id == assignment_id, Assignment.campaign_id == campaign_id
            ),
            area,
            Assignment,
        ).options(*WITH_DETAIL),
        "assignment",
    )


async def _member(
    session: AsyncSession, campaign: Campaign, details: dict
) -> tuple[Mobilizer | None, Agent | None]:
    """The mobilizer or agent named, who must belong to this workspace."""
    if details.get("mobilizer") and not details.get("agent"):
        return await campaign_mobilizer(session, campaign.id, details["mobilizer"]), None
    if details.get("agent") and not details.get("mobilizer"):
        found = await session.get(Agent, details["agent"])
        if found is None or found.campaign_id != campaign.id:
            raise Refused("No such agent on this campaign.")
        return None, found
    raise Refused("Name one mobilizer or one agent.")


async def _place(
    session: AsyncSession,
    campaign: Campaign,
    details: dict,
    mobilizer: Mobilizer | None,
    agent: Agent | None,
) -> tuple[Event | None, uuid.UUID | None, uuid.UUID | None]:
    """The event, ward and centre the work happens at."""
    kind = details["kind"]
    if kind is AssignmentKind.EVENT:
        event = await session.get(Event, details.get("event")) if details.get("event") else None
        if event is None or event.campaign_id != campaign.id:
            raise Refused("Pick an event on this campaign.")
        if event.status is EventStatus.CANCELLED:
            raise Refused("That event was cancelled.")
        return event, event.ward_id, event.registration_centre_id
    if kind is AssignmentKind.WARD_WORK:
        centre_id = details.get("registration_centre")
        ward_id = details.get("ward")
        if centre_id:
            ward_id = (await require_centre(session, campaign, centre_id)).ward_id
        else:
            await require_ward(session, campaign, ward_id)
        return None, ward_id, centre_id
    member = mobilizer or agent
    if member.ward_id is None:
        raise Refused("Give them a ward or centre before assigning them an activity.")
    if not (details.get("description") or "").strip():
        raise Refused("Say what the activity is.")
    return None, member.ward_id, member.registration_centre_id


async def create(
    session: AsyncSession, campaign: Campaign, details: dict, area: Area | None, *, actor: User
) -> Assignment:
    """Give a mobilizer or agent some work; both they and the place must lie in the caller's
    area."""
    mobilizer, agent = await _member(session, campaign, details)
    member = mobilizer or agent
    if area is not None and not area.holds(member.ward_id, member.registration_centre_id):
        raise Refused("That person works outside your area.")
    event, ward_id, centre_id = await _place(session, campaign, details, mobilizer, agent)
    if area is not None and not area.holds(ward_id, centre_id):
        raise Refused("That place is outside your area.")
    row = Assignment(
        campaign_id=campaign.id,
        mobilizer_id=mobilizer.id if mobilizer else None,
        agent_id=agent.id if agent else None,
        kind=details["kind"],
        event_id=event.id if event else None,
        ward_id=ward_id,
        registration_centre_id=centre_id,
        description=(details.get("description") or "").strip(),
        amount_kes=details["amount_kes"],
        created_by_id=actor.id,
    )
    session.add(row)
    await session.flush()
    record(
        session,
        actor=actor,
        action="assignment.create",
        subject_type="assignment",
        subject_id=row.id,
        campaign_id=campaign.id,
        detail={"kind": row.kind.value, "amount_kes": row.amount_kes},
    )
    await session.commit()
    return await assignment(session, campaign.id, row.id, None)


async def settle(
    session: AsyncSession,
    campaign: Campaign,
    row: Assignment,
    outcome: AssignmentStatus,
    *,
    actor: User,
) -> Assignment:
    """Mark an assigned piece of work done, or cancel it; each happens once."""
    values: dict = {"status": outcome}
    if outcome is AssignmentStatus.DONE:
        values |= {"done_by_id": actor.id, "done_at": datetime.now(UTC)}
    await move_row(
        session,
        row,
        f"That assignment is already {row.status.label.lower()}.",
        Assignment.status == AssignmentStatus.ASSIGNED,
        **values,
    )
    record(
        session,
        actor=actor,
        action=f"assignment.{outcome.value}",
        subject_type="assignment",
        subject_id=row.id,
        campaign_id=campaign.id,
    )
    row_id = row.id
    await session.commit()
    session.expire(row)
    return await assignment(session, campaign.id, row_id, None)
