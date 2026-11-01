"""CRM plans, each campaign's subscription, and the ledger that sets its paid date."""

import uuid
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_type
from backend.models.enums import EntryKind, ReceiptMethod, SubscriptionHold

if TYPE_CHECKING:
    from backend.models.campaign import Campaign
    from backend.models.user import User

LIVE_PAYMENT = "kind = 'payment' AND voided_at IS NULL"


def _updated_at() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
        sort_order=101,
    )


class CrmPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A price for a length of CRM access. Deactivated, never deleted."""

    __tablename__ = "crm_plans"
    __table_args__ = (
        UniqueConstraint("name", name="uq_crm_plans_name"),
        CheckConstraint("price_kes >= 0", name="price_not_negative"),
        CheckConstraint("duration_days BETWEEN 1 AND 730", name="duration_range"),
    )

    name: Mapped[str] = mapped_column(String(80))
    price_kes: Mapped[int] = mapped_column(Integer)
    duration_days: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = _updated_at()


class CampaignSubscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One campaign's plan, last paid day and hold; kept after the campaign is deleted."""

    __tablename__ = "campaign_subscriptions"
    __table_args__ = (
        UniqueConstraint("campaign_id", name="uq_campaign_subscriptions_campaign_id"),
        CheckConstraint("(hold = 'none') = (hold_reason IS NULL)", name="hold_has_reason"),
    )

    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="SET NULL"), default=None
    )
    # Written just before the campaign is deleted, so the record keeps its name.
    campaign_title: Mapped[str | None] = mapped_column(String(150), default=None)
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("crm_plans.id", ondelete="RESTRICT"), default=None
    )
    # The last day of paid access, inclusive.
    paid_until: Mapped[date | None] = mapped_column(Date, default=None)
    hold: Mapped[SubscriptionHold] = mapped_column(
        choice_type(SubscriptionHold, "subscription_hold"), default=SubscriptionHold.NONE
    )
    hold_reason: Mapped[str | None] = mapped_column(Text, default=None)
    updated_at: Mapped[datetime] = _updated_at()

    campaign: Mapped["Campaign | None"] = relationship(back_populates="subscription")
    plan: Mapped[CrmPlan | None] = relationship()
    entries: Mapped[list["SubscriptionEntry"]] = relationship(
        back_populates="subscription", order_by="SubscriptionEntry.created_at"
    )


class SubscriptionEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A payment or a free extension, and the paid date before and after it."""

    __tablename__ = "subscription_entries"
    __table_args__ = (
        CheckConstraint(
            "(kind = 'payment' AND amount_kes > 0 AND method IS NOT NULL "
            "AND reference IS NOT NULL AND plan_id IS NOT NULL) "
            "OR (kind = 'extension' AND amount_kes IS NULL AND method IS NULL "
            "AND reference IS NULL)",
            name="entry_shape",
        ),
        CheckConstraint("days BETWEEN 1 AND 730", name="days_range"),
        Index(
            "uq_subscription_entries_reference",
            "reference",
            unique=True,
            sqlite_where=text(LIVE_PAYMENT),
            postgresql_where=text(LIVE_PAYMENT),
        ),
        Index(
            "ix_subscription_entries_subscription_id_created_at", "subscription_id", "created_at"
        ),
    )

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("campaign_subscriptions.id", ondelete="RESTRICT")
    )
    kind: Mapped[EntryKind] = mapped_column(choice_type(EntryKind, "entry_kind"))
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("crm_plans.id", ondelete="RESTRICT"), default=None
    )
    amount_kes: Mapped[int | None] = mapped_column(Integer, default=None)
    method: Mapped[ReceiptMethod | None] = mapped_column(
        choice_type(ReceiptMethod, "receipt_method"), default=None
    )
    # Trimmed and upper-cased, so one M-Pesa code is one reference.
    reference: Mapped[str | None] = mapped_column(String(40), default=None)
    received_on: Mapped[date] = mapped_column(Date)
    days: Mapped[int] = mapped_column(Integer)
    paid_until_before: Mapped[date | None] = mapped_column(Date, default=None)
    paid_until_after: Mapped[date] = mapped_column(Date)
    note: Mapped[str] = mapped_column(Text, default="")
    recorded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    voided_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    void_reason: Mapped[str | None] = mapped_column(Text, default=None)

    subscription: Mapped[CampaignSubscription] = relationship(back_populates="entries")
    plan: Mapped[CrmPlan | None] = relationship()
    recorded_by: Mapped["User | None"] = relationship(foreign_keys=[recorded_by_id])
