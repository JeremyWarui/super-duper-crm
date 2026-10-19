"""Money paid to a mobilizer for an event, recorded once and never edited after it is paid."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_type
from backend.models.enums import PaymentStatus

if TYPE_CHECKING:
    from backend.models.event import Event
    from backend.models.mobilizer import Mobilizer


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
    # The M-Pesa or bank reference the money moved under.
    reference: Mapped[str] = mapped_column(String(50), default="")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    event: Mapped["Event | None"] = relationship()
    mobilizer: Mapped["Mobilizer | None"] = relationship()

    def __str__(self) -> str:
        return f"KES {self.amount_kes:,} to {self.recipient_name} ({self.status.label})"
