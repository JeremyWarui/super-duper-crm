"""A workspace's polling agents, their coverage of registration centres, and the export for
appointment letters."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from backend.api.csv_export import cell, csv_response
from backend.api.deps import SessionDep, require
from backend.api.scope import area_of, require_visible_campaign
from backend.models import Agent, User
from backend.schemas.team_signup import AgentRead, AgentUpdate, Coverage, CoverageCentre
from backend.services import agents
from backend.services.audit import record
from backend.services.errors import Forbidden, NotFound
from backend.services.permissions import Reach, reach

router = APIRouter(prefix="/agents", tags=["agents"])

Reader = Annotated[User, Depends(require("agents.read"))]
Writer = Annotated[User, Depends(require("agents.write"))]
Exporter = Annotated[User, Depends(require("export"))]
CSV_COLUMNS = ["centre", "ward", "agent", "phone", "email", "id_number", "status", "training_date"]


def _read(row: Agent, id_number: str | None) -> AgentRead:
    return AgentRead(
        id=row.id,
        full_name=row.user.display_name,
        phone=row.user.phone,
        email=row.user.email,
        id_number=id_number,
        registration_centre=row.registration_centre_id,
        centre_name=row.registration_centre.name if row.registration_centre else None,
        ward_name=row.ward.name if row.ward else None,
        status=row.status,
        training_date=row.training_date,
    )


async def _with_ids(session: SessionDep, user: User, rows: list[Agent]) -> list[AgentRead]:
    """ID numbers for the candidate and manager, and for an agent reading their own row."""
    found = reach(user, "team.id_read")
    shown = await agents.id_numbers(session, [row.user_id for row in rows]) if found else {}
    return [
        _read(
            row,
            shown.get(row.user_id) if found is Reach.ALL or row.user_id == user.id else None,
        )
        for row in rows
    ]


@router.get("/", response_model=list[AgentRead])
async def list_agents(campaign: uuid.UUID, session: SessionDep, user: Reader) -> list[AgentRead]:
    """The caller's agents: all of them, a coordinator's area, or an agent's own row."""
    await require_visible_campaign(session, user, campaign)
    if reach(user, "agents.read") is Reach.OWN:
        rows = await agents.agents(session, campaign, None, own=user.id)
    else:
        rows = await agents.agents(session, campaign, await area_of(session, user, "agents.read"))
    return await _with_ids(session, user, rows)


@router.get("/coverage/", response_model=Coverage)
async def coverage(campaign: uuid.UUID, session: SessionDep, user: Reader) -> Coverage:
    """How many centres in the caller's reach have an agent, and which have none."""
    if reach(user, "agents.read") is Reach.OWN:
        raise Forbidden("Coverage is for the campaign team.")
    found = await require_visible_campaign(session, user, campaign)
    total, covered, missing, more = await agents.coverage(
        session, found, await area_of(session, user, "agents.read")
    )
    return Coverage(
        centres=total,
        covered=covered,
        uncovered=[CoverageCentre(id=c.id, name=c.name, ward_name=ward) for c, ward in missing],
        more_uncovered=more,
    )


@router.get("/export/")
async def export(campaign: uuid.UUID, session: SessionDep, user: Exporter) -> Response:
    """Every agent with their centre and ID number, as CSV for appointment letters; audited."""
    await require_visible_campaign(session, user, campaign)
    rows = await agents.agents(session, campaign, None)
    ids = await agents.id_numbers(session, [row.user_id for row in rows])
    record(
        session,
        actor=user,
        action="agent.export",
        subject_type="agent",
        campaign_id=campaign,
        detail={"rows": len(rows)},
    )
    await session.commit()
    return csv_response(
        "agents.csv",
        CSV_COLUMNS,
        (
            [
                cell(row.registration_centre.name if row.registration_centre else ""),
                cell(row.ward.name if row.ward else ""),
                cell(row.user.display_name),
                row.user.phone,
                cell(row.user.email),
                ids.get(row.user_id, ""),
                row.status.value,
                row.training_date.isoformat() if row.training_date else "",
            ]
            for row in rows
        ),
    )


@router.patch("/{agent_id}/", response_model=AgentRead)
async def update_agent(
    agent_id: uuid.UUID, payload: AgentUpdate, session: SessionDep, user: Writer
) -> AgentRead:
    """Move an agent to a centre, or set their vetting status or training date."""
    row = await session.get(Agent, agent_id)
    if row is None:
        raise NotFound("No such agent.")
    campaign = await require_visible_campaign(session, user, row.campaign_id)
    area = await area_of(session, user, "agents.write")
    row = await agents.agent(session, campaign.id, agent_id, area)
    updated = await agents.update(
        session, campaign, row, payload.model_dump(exclude_unset=True), area, actor=user
    )
    return (await _with_ids(session, user, [updated]))[0]
