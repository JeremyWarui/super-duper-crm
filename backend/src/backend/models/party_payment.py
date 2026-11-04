"""Money the party pays out to agents, volunteers, members and staff, for a campaign or none."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_type
from backend.models.enums import PayeeKind
from backend.models.payment import PayoutMixin


class PartyPayment(PayoutMixin, UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "party_payments"
    __table_args__ = (
        CheckConstraint("amount_kes > 0", name="amount_kes_positive"),
        CheckConstraint("member_id IS NULL OR volunteer_id IS NULL", name="one_register"),
    )

    payee_kind: Mapped[PayeeKind] = mapped_column(choice_type(PayeeKind, "payee_kind"))
    # The register row the payee was picked from; both NULL when typed in by hand.
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("party_members.id", ondelete="SET NULL"), default=None, index=True
    )
    volunteer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("volunteer_profiles.id", ondelete="SET NULL"), default=None, index=True
    )
    registration_centre_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("registration_centres.id", ondelete="SET NULL"), default=None
    )
    polling_station: Mapped[str] = mapped_column(String(200), default="")

    # The approved aspirant, and so the campaign, the money is spent on; NULL for party work.
    aspirant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("aspirants.id", ondelete="SET NULL"), default=None, index=True
    )
    # "Achieng Otieno · MCA · Githurai" as it stood when scheduled.
    campaign_label: Mapped[str] = mapped_column(String(200), default="")
    purpose: Mapped[str] = mapped_column(String(150), default="")

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    # The party super admin who let it go out; release and marking paid wait for this.
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    approved_by_name: Mapped[str] = mapped_column(String(150), default="")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
