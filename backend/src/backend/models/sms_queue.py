"""Bulk texts through the compliance queue: one run per approved message, one outbox row per
number (CD-R6 section 5.5)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, campaign_ref, user_ref

RUN_STAGES = ("awaiting_vetting", "scheduled", "sending", "paused", "halted", "completed")
OUTBOX_STATES = ("queued", "sending", "sent", "failed", "skipped")


class SmsRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One approved message on its way out, a batch at a time."""

    __tablename__ = "sms_runs"

    campaign_id: Mapped[uuid.UUID] = campaign_ref()
    message_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("campaign_messages.id", ondelete="CASCADE"), unique=True
    )
    # Set for an event invitation; the event's number reached follows what the run sent.
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("events.id", ondelete="SET NULL"), default=None
    )
    status: Mapped[str] = mapped_column(String(20), default="sending")
    language: Mapped[str] = mapped_column(String(2))
    # The candidate's name as registered, which the text had to carry.
    sender_name: Mapped[str] = mapped_column(String(150), default="")
    # The whole text each person receives, opt-out line included.
    text: Mapped[str] = mapped_column(Text)
    vetting_ref: Mapped[str] = mapped_column(String(100), default="")
    vetted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    targeted: Mapped[int] = mapped_column(Integer, default=0)
    excluded_no_consent: Mapped[int] = mapped_column(Integer, default=0)
    excluded_opted_out: Mapped[int] = mapped_column(Integer, default=0)
    sent: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    segments: Mapped[int] = mapped_column(Integer, default=1)
    estimated_cost_cents: Mapped[int] = mapped_column(Integer, default=0)
    actual_cost_cents: Mapped[int] = mapped_column(Integer, default=0)
    approved_by_id: Mapped[uuid.UUID | None] = user_ref()
    halted_by_id: Mapped[uuid.UUID | None] = user_ref()
    halt_reason: Mapped[str] = mapped_column(Text, default="")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class SmsOutbox(UUIDPrimaryKeyMixin, Base):
    """One number in a run; the unique key means no retry can text the same person twice."""

    __tablename__ = "sms_outbox"
    __table_args__ = (UniqueConstraint("run_id", "phone", name="uq_sms_outbox_run_phone"),)

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sms_runs.id", ondelete="CASCADE"), index=True
    )
    supporter_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("supporters.id", ondelete="SET NULL"), default=None
    )
    phone: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    skip_reason: Mapped[str] = mapped_column(String(40), default="")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    sms_log_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("sms_log.id", ondelete="SET NULL"), default=None
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # The idempotency key of the batch this row went in; a retried batch keeps it.
    batch_key: Mapped[str] = mapped_column(String(64), default="", server_default="")
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
