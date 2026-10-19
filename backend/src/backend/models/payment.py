"""Money paid to a mobilizer for an event, recorded once and never edited after it is paid."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_type
from backend.models.enums import PaymentStatus

if TYPE_CHECKING:
    from backend.models.event import Event
    from backend.models.mobilizer import Mobilizer


# A send unanswered for this long is settled by a person, after checking the provider.
STUCK_AFTER = timedelta(minutes=2)
OUTCOME_UNKNOWN = "Outcome unknown: check the payout provider, then mark it paid or not sent."


class Payment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount_kes > 0", name="amount_kes_positive"),
        # One live payment per mobilizer per event; a cancelled one does not count.
        Index(
            "uq_payments_event_mobilizer",
            "event_id",
            "mobilizer_id",
            unique=True,
            postgresql_where=text("status <> 'cancelled'"),
            sqlite_where=text("status <> 'cancelled'"),
        ),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("events.id", ondelete="SET NULL"), default=None, index=True
    )
    mobilizer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("mobilizers.id", ondelete="SET NULL"), default=None, index=True
    )

    # Who was paid and for what, as they stood when scheduled; kept if the rows go.
    recipient_name: Mapped[str] = mapped_column(String(150))
    recipient_phone: Mapped[str] = mapped_column(String(20), default="")
    event_title: Mapped[str] = mapped_column(String(150), default="")

    amount_kes: Mapped[int] = mapped_column(Integer)
    status: Mapped[PaymentStatus] = mapped_column(
        choice_type(PaymentStatus, "payment_status"), default=PaymentStatus.SCHEDULED
    )
    # The M-Pesa, bank or provider reference the money moved under.
    reference: Mapped[str] = mapped_column(String(50), default="", index=True)
    # The payout provider that sent it ("practice", later "paystack"); blank when marked by hand.
    provider: Mapped[str] = mapped_column(String(20), default="")
    failure_reason: Mapped[str] = mapped_column(String(200), default="")
    # Each release is a new attempt; a provider's answer lands only on the attempt it belongs to.
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    sending_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    event: Mapped["Event | None"] = relationship()
    mobilizer: Mapped["Mobilizer | None"] = relationship()

    def __str__(self) -> str:
        return f"KES {self.amount_kes:,} to {self.recipient_name} ({self.status.label})"

    @property
    def stuck(self) -> bool:
        """Sending with no answer to wait for: the outcome is unknown, or it has gone quiet."""
        if self.status is not PaymentStatus.SENDING:
            return False
        if self.failure_reason == OUTCOME_UNKNOWN or self.sending_since is None:
            return True
        since = self.sending_since
        if since.tzinfo is None:
            since = since.replace(tzinfo=UTC)
        return datetime.now(UTC) - since > STUCK_AFTER
