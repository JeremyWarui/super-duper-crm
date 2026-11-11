"""Money paid in by M-Pesa: nomination fees and website contributions."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_type, user_ref
from backend.models.enums import PayInMethod, PayInPurpose, PayInStatus


class PaymentIn(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One attempt to pay. `campaign_id` NULL is money for the party; `aspirant_id` is set for a
    nomination fee."""

    __tablename__ = "payments_in"

    purpose: Mapped[PayInPurpose] = mapped_column(choice_type(PayInPurpose, "pay_in_purpose"))
    method: Mapped[PayInMethod] = mapped_column(choice_type(PayInMethod, "pay_in_method"))
    status: Mapped[PayInStatus] = mapped_column(
        choice_type(PayInStatus, "pay_in_status"), default=PayInStatus.PENDING, index=True
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="SET NULL"), default=None, index=True
    )
    aspirant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("aspirants.id", ondelete="SET NULL"), default=None, index=True
    )
    amount_kes: Mapped[int] = mapped_column(Integer)
    payer_name: Mapped[str] = mapped_column(String(150))
    payer_phone: Mapped[str] = mapped_column(String(20))
    payer_email: Mapped[str] = mapped_column(String(254), default="")
    # Ours, sent to Paystack as the charge reference; unguessable, so it also reads the status.
    reference: Mapped[str] = mapped_column(String(64), unique=True)
    # The M-Pesa confirmation code: typed by the payer, or Paystack's receipt.
    mpesa_code: Mapped[str] = mapped_column(String(20), default="")
    # practice, paystack or manual.
    provider: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(300), default="")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    decided_by_id: Mapped[uuid.UUID | None] = user_ref()
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
