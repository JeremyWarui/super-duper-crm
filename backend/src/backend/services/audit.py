"""The audit trail: events are added inside the caller's transaction and never changed."""

import uuid
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import Boolean, insert, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AuditEvent, User


def record(
    session: AsyncSession,
    *,
    actor: User | None,
    action: str,
    subject_type: str,
    subject_id: uuid.UUID | None = None,
    campaign_id: uuid.UUID | None = None,
    detail: dict | None = None,
    actor_name: str = "cli",
) -> AuditEvent:
    """Add an event to the session; the caller's commit or rollback decides whether it stays."""
    event = AuditEvent(
        actor_id=actor.id if actor else None,
        actor_name=actor.username if actor else actor_name,
        action=action,
        subject_type=subject_type,
        subject_id=subject_id,
        campaign_id=campaign_id,
        detail=detail or {},
    )
    session.add(event)
    return event


async def record_if(
    session: AsyncSession,
    write: bool,
    *,
    actor_name: str,
    action: str,
    subject_type: str,
    subject_id: uuid.UUID | None,
    detail: dict,
) -> None:
    """Add an event without a login only when `write` holds.

    Runs the same single statement either way, so the work does not show whether it wrote.
    """
    columns = AuditEvent.__table__.c
    values = {
        "id": uuid.uuid4(),
        "created_at": datetime.now(UTC),
        "actor_id": None,
        "actor_name": actor_name,
        "action": action,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "campaign_id": None,
        "detail": detail,
    }
    row = select(*(literal(v, columns[k].type).label(k) for k, v in values.items())).where(
        literal(write, Boolean)
    )
    await session.execute(insert(AuditEvent).from_select(list(values), row))


async def events(
    session: AsyncSession,
    *,
    subject_type: str | None = None,
    subject_id: uuid.UUID | None = None,
    action: str | None = None,
    actor: str | None = None,
    since: date | None = None,
    until: date | None = None,
    limit: int = 100,
) -> list[AuditEvent]:
    """The newest events first, optionally for one subject; `action` matches its start (so
    "import" finds every import), `actor` part of the name, and the dates are inclusive."""
    query = select(AuditEvent).order_by(AuditEvent.created_at.desc(), AuditEvent.id).limit(limit)
    if action:
        query = query.where(AuditEvent.action.startswith(action, autoescape=True))
    if actor:
        query = query.where(AuditEvent.actor_name.icontains(actor, autoescape=True))
    if since is not None:
        query = query.where(AuditEvent.created_at >= datetime.combine(since, time.min, UTC))
    if until is not None:
        query = query.where(
            AuditEvent.created_at < datetime.combine(until + timedelta(days=1), time.min, UTC)
        )
    if subject_type is not None:
        query = query.where(AuditEvent.subject_type == subject_type)
    if subject_id is not None:
        query = query.where(AuditEvent.subject_id == subject_id)
    return list(await session.scalars(query))
