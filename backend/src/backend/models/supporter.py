"""Someone who signed up for a campaign, and where they stand."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    campaign_ref,
    choice_type,
    partial_unique,
)
from backend.models.enums import ConsentChannel, SupportLevel

if TYPE_CHECKING:
    from backend.models.campaign import Campaign
    from backend.models.geography import Ward
    from backend.models.mobilizer import Mobilizer


class Supporter(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "supporters"
    __table_args__ = (
        # One person per phone number per campaign.
        partial_unique(
            "uq_supporters_campaign_phone",
            "campaign_id",
            "phone",
            where="phone <> ''",
        ),
    )

    campaign_id: Mapped[uuid.UUID] = campaign_ref()
    ward_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("wards.id", ondelete="SET NULL"), default=None, index=True
    )
    # The mobilizer who signed them up, if anyone did.
    mobilizer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("mobilizers.id", ondelete="SET NULL"), default=None, index=True
    )

    # Their registration centre, kept in a ward (MCA) race, which counts per centre.
    registration_centre_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("registration_centres.id", ondelete="SET NULL"), default=None, index=True
    )
    # The event whose sign-up link they used, if any.
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("events.id", ondelete="SET NULL"), default=None, index=True
    )

    full_name: Mapped[str] = mapped_column(String(150))
    phone: Mapped[str] = mapped_column(String(20), default="")
    support_level: Mapped[SupportLevel] = mapped_column(
        choice_type(SupportLevel, "support_level"), default=SupportLevel.UNDECIDED
    )

    # Consent to hold their data, required by the Data Protection Act 2019.
    consent_given: Mapped[bool] = mapped_column(Boolean, default=False)
    # The channel they signed up through and the wording shown there; None for older rows.
    consent_channel: Mapped[ConsentChannel | None] = mapped_column(
        choice_type(ConsentChannel, "consent_channel"), default=None
    )
    consent_wording: Mapped[str | None] = mapped_column(Text, default=None)

    # The private code a self-signed supporter withdraws with; None for anyone else.
    withdraw_code: Mapped[str | None] = mapped_column(String(32), unique=True, default=None)
    # Personal fields blanked on request; the row stays for counts.
    erased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    campaign: Mapped["Campaign"] = relationship(back_populates="supporters")
    ward: Mapped["Ward | None"] = relationship(back_populates="supporters")
    mobilizer: Mapped["Mobilizer | None"] = relationship(back_populates="supporters")

    def __str__(self) -> str:
        return self.full_name
