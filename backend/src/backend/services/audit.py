"""The audit trail: events are added inside the caller's transaction and never changed."""

import uuid

from sqlalchemy import select
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
) -> AuditEvent:
    """Add an event to the session; the caller's commit or rollback decides whether it stays."""
    event = AuditEvent(
        actor_id=actor.id if actor else None,
        actor_name=actor.username if actor else "cli",
        action=action,
        subject_type=subject_type,
        subject_id=subject_id,
        campaign_id=campaign_id,
        detail=detail or {},
    )
    session.add(event)
    return event


async def events(
    session: AsyncSession,
    *,
    subject_type: str | None = None,
    subject_id: uuid.UUID | None = None,
    limit: int = 100,
) -> list[AuditEvent]:
    """The newest events first, optionally for one subject."""
    query = select(AuditEvent).order_by(AuditEvent.created_at.desc(), AuditEvent.id).limit(limit)
    if subject_type is not None:
        query = query.where(AuditEvent.subject_type == subject_type)
    if subject_id is not None:
        query = query.where(AuditEvent.subject_id == subject_id)
    return list(await session.scalars(query))
