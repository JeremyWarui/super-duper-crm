"""A record of one sensitive action, kept after the rows it touched are gone."""

import uuid

from sqlalchemy import JSON, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AuditEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Who did what to which row. The subject and campaign ids carry no foreign key."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_subject_type_subject_id", "subject_type", "subject_id"),
        Index("ix_audit_events_created_at", "created_at"),
    )

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    actor_name: Mapped[str] = mapped_column(String(150))
    action: Mapped[str] = mapped_column(String(60))
    subject_type: Mapped[str] = mapped_column(String(40))
    subject_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
