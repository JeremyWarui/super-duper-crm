"""Money paid out: to a mobilizer for an event, recorded once and never edited after it is paid."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    campaign_ref,
    choice_type,
    partial_unique,
    user_ref,
)
from backend.models.enums import PaymentStatus, UserRole
from backend.services.clock import as_utc

if TYPE_CHECKING:
    from backend.models.event import Event
    from backend.models.mobilizer import Mobilizer


# A send unanswered for this long is settled by a person, after checking the provider.
STUCK_AFTER = timedelta(minutes=2)
OUTCOME_UNKNOWN = "Outcome unknown: check the payout provider, then mark it paid or not sent."


class PayoutMixin:
    """Who is paid, how much, and where the send stands; shared by every payment table."""

    # Who was paid, as they stood when scheduled; kept if the rows go.
    recipient_name: Mapped[str] = mapped_column(String(150))
    recipient_phone: Mapped[str] = mapped_column(String(20), default="")

    amount_kes: Mapped[int] = mapped_column(Integer)
    status: Mapped[PaymentStatus] = mapped_column(
        choice_type(PaymentStatus, "payment_status"), default=PaymentStatus.SCHEDULED
    )
    # The M-Pesa, bank or provider reference the money moved under.
    reference: Mapped[str] = mapped_column(String(50), default="", index=True)
    # The payout provider that sent it ("practice" or "paystack"); blank when marked by hand.
    provider: Mapped[str] = mapped_column(String(20), default="")
    failure_reason: Mapped[str] = mapped_column(String(200), default="")
    # Each release is a new attempt; a provider's answer lands only on the attempt it belongs to.
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    sending_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    def __str__(self) -> str:
        return f"KES {self.amount_kes:,} to {self.recipient_name} ({self.status.label})"

    @property
    def stuck(self) -> bool:
        """Sending with no answer to wait for: the outcome is unknown, or it has gone quiet."""
        if self.status is not PaymentStatus.SENDING:
            return False
        if self.failure_reason == OUTCOME_UNKNOWN or self.sending_since is None:
            return True
        return datetime.now(UTC) - as_utc(self.sending_since) > STUCK_AFTER


class Payment(PayoutMixin, UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount_kes > 0", name="amount_kes_positive"),
        # One live payment per mobilizer per event; a cancelled one does not count.
        partial_unique(
            "uq_payments_event_mobilizer",
            "event_id",
            "mobilizer_id",
            where="status <> 'cancelled'",
        ),
        # One live payment per assignment.
        partial_unique(
            "uq_payments_assignment",
            "assignment_id",
            where="status <> 'cancelled'",
        ),
    )

    campaign_id: Mapped[uuid.UUID] = campaign_ref()
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("events.id", ondelete="SET NULL"), default=None, index=True
    )
    mobilizer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("mobilizers.id", ondelete="SET NULL"), default=None, index=True
    )
    # What it pays for, as it stood when scheduled: the event's title or the assignment's label.
    event_title: Mapped[str] = mapped_column(String(150), default="")
    # The done assignment it pays; None only on payments made before assignments existed.
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("assignments.id", ondelete="SET NULL"), default=None, index=True
    )
    # The payee when it is an agent; a mobilizer payee is `mobilizer_id`.
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("agents.id", ondelete="SET NULL"), default=None, index=True
    )
    scheduled_by_id: Mapped[uuid.UUID | None] = user_ref()
    # The role that approves and releases it (decision 27); None means the manager.
    approver_role: Mapped[UserRole | None] = mapped_column(
        choice_type(UserRole, "approver_role"), default=None
    )
    approved_by_id: Mapped[uuid.UUID | None] = user_ref()

    event: Mapped["Event | None"] = relationship()
    mobilizer: Mapped["Mobilizer | None"] = relationship()


class ReconcileRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One comparison of the payments ledger with the payout provider's own records.

    `status` is `matched`, `differences`, `failed` (the provider could not be read) or
    `practice` (the provider keeps no records to compare).
    """

    __tablename__ = "reconcile_runs"

    provider: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    checked: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[str] = mapped_column(Text, default="")

    differences: Mapped[list["ReconcileDifference"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )


class ReconcileDifference(UUIDPrimaryKeyMixin, Base):
    """Where the ledger and the provider disagree about one payment's transfer."""

    __tablename__ = "reconcile_differences"

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("reconcile_runs.id", ondelete="CASCADE"), index=True
    )
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("payments.id", ondelete="SET NULL"), index=True, default=None
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="CASCADE"), index=True, default=None
    )
    reference: Mapped[str] = mapped_column(String(100), default="")
    ledger: Mapped[str] = mapped_column(String(100), default="")
    provider: Mapped[str] = mapped_column(String(100), default="")
    detail: Mapped[str] = mapped_column(Text, default="")

    run: Mapped["ReconcileRun"] = relationship(back_populates="differences")
