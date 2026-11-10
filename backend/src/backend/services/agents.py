"""A workspace's polling agents: who they are, which centre each readies for, and which centres
still have none."""

import uuid

from sqlalchemy import Select, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    Agent,
    Campaign,
    OfficeLevel,
    RegistrationCentre,
    TeamRegistration,
    User,
    Ward,
)
from backend.services.audit import record
from backend.services.errors import NotFound, Refused
from backend.services.permissions import Area, narrow
from backend.services.targets import _in_area, ward_in_area

# Centres without an agent listed by the coverage view; the rest are counted.
UNCOVERED_LIMIT = 500
WITH_PEOPLE = (
    selectinload(Agent.user),
    selectinload(Agent.ward),
    selectinload(Agent.registration_centre),
)


async def agents(
    session: AsyncSession, campaign_id: uuid.UUID, area: Area | None, own: uuid.UUID | None = None
) -> list[Agent]:
    """The workspace's agents inside `area`, or only the login `own`, by centre then name."""
    statement = select(Agent).where(Agent.campaign_id == campaign_id).options(*WITH_PEOPLE)
    statement = statement.where(Agent.user_id == own) if own else narrow(statement, area, Agent)
    found = list(await session.scalars(statement))
    return sorted(
        found,
        key=lambda a: (
            a.registration_centre.name if a.registration_centre else "~",
            a.user.full_name,
        ),
    )


async def id_numbers(session: AsyncSession, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """Each login's ID number, from the sign-up that made it."""
    rows = await session.execute(
        select(TeamRegistration.user_id, TeamRegistration.id_number).where(
            TeamRegistration.user_id.in_(user_ids)
        )
    )
    return dict(rows.all())


async def agent(
    session: AsyncSession, campaign_id: uuid.UUID, agent_id: uuid.UUID, area: Area | None
) -> Agent:
    found = await session.scalar(
        narrow(
            select(Agent).where(Agent.id == agent_id, Agent.campaign_id == campaign_id), area, Agent
        ).options(*WITH_PEOPLE)
    )
    if found is None:
        raise NotFound("No such agent.")
    return found


async def update(
    session: AsyncSession,
    campaign: Campaign,
    row: Agent,
    changes: dict,
    area: Area | None,
    *,
    actor: User,
) -> Agent:
    """Move an agent to a centre (inside the seat, and the caller's area), or set their
    vetting status or training date."""
    if "registration_centre" in changes:
        centre_id = changes["registration_centre"]
        if centre_id is None and area is not None:
            raise Refused("Move the agent to a centre in your area instead.")
        centre = await session.get(RegistrationCentre, centre_id) if centre_id else None
        if centre_id is not None and (
            centre is None or not await ward_in_area(session, campaign, centre.ward_id)
        ):
            raise Refused("That registration centre is not one this campaign works.")
        if centre is not None and area is not None and not area.holds(centre.ward_id, centre.id):
            raise Refused("That registration centre is outside your area.")
        row.registration_centre_id = centre.id if centre else None
        row.ward_id = centre.ward_id if centre else None
    if changes.get("status") is not None:
        row.status = changes["status"]
    if "training_date" in changes:
        row.training_date = changes["training_date"]
    record(
        session,
        actor=actor,
        action="agent.update",
        subject_type="agent",
        subject_id=row.id,
        campaign_id=campaign.id,
        detail={key: str(value) for key, value in changes.items()},
    )
    await session.commit()
    return await agent(session, campaign.id, row.id, None)


def _centres(campaign: Campaign, area: Area | None) -> Select | None:
    """The registration centres in the seat, and in `area` when given."""
    statement = (
        select(RegistrationCentre)
        .join(Ward, Ward.id == RegistrationCentre.ward_id)
        .where(RegistrationCentre.retired.is_(False))
    )
    if campaign.office_level is OfficeLevel.WARD:
        statement = statement.where(Ward.id == campaign.ward_id)
    else:
        statement = _in_area(statement, campaign)
        if statement is None:
            return None
    if area is not None:
        statement = statement.where(area.where(RegistrationCentre.ward_id, RegistrationCentre.id))
    return statement


async def coverage(
    session: AsyncSession, campaign: Campaign, area: Area | None
) -> tuple[int, int, list[tuple[RegistrationCentre, str]], int]:
    """Centres in reach, how many have an agent, and the first centres without one."""
    centres = _centres(campaign, area)
    if centres is None:
        return 0, 0, [], 0
    ids = centres.with_only_columns(RegistrationCentre.id).subquery()
    total = await session.scalar(select(func.count()).select_from(ids))
    covered = await session.scalar(
        select(func.count(distinct(Agent.registration_centre_id))).where(
            Agent.campaign_id == campaign.id, Agent.registration_centre_id.in_(select(ids.c.id))
        )
    )
    with_agent = select(Agent.registration_centre_id).where(
        Agent.campaign_id == campaign.id, Agent.registration_centre_id.is_not(None)
    )
    uncovered = (
        await session.execute(
            centres.where(RegistrationCentre.id.not_in(with_agent))
            .add_columns(Ward.name)
            .order_by(Ward.name, RegistrationCentre.name)
            .limit(UNCOVERED_LIMIT)
        )
    ).all()
    missing = total - covered
    return total, covered, [(c, ward) for c, ward in uncovered], max(missing - len(uncovered), 0)
