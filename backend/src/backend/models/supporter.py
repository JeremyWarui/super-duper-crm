"""A supporter, captured by public self-registration or by a mobilizer."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_type
from backend.models.enums import SupportLevel

if TYPE_CHECKING:
    from backend.models.campaign import Campaign
    from backend.models.geography import Ward
    from backend.models.mobilizer import Mobilizer


class Supporter(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Django called the timestamp `registered_at`; it is `created_at` here, from
    the shared mixin, so every table names its creation time the same way.
    Default ordering was `-registered_at`.
    """

    __tablename__ = "supporters"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    ward_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("wards.id", ondelete="SET NULL"), default=None, index=True
    )
    mobilizer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("mobilizers.id", ondelete="SET NULL"), default=None, index=True
    )

    full_name: Mapped[str] = mapped_column(String(150))
    phone: Mapped[str] = mapped_column(String(20), default="")
    support_level: Mapped[SupportLevel] = mapped_column(
        choice_type(SupportLevel, "support_level"), default=SupportLevel.UNDECIDED
    )

    # Data Protection Act 2019 - consent captured at sign-up.
    consent_given: Mapped[bool] = mapped_column(Boolean, default=False)

    campaign: Mapped["Campaign"] = relationship(back_populates="supporters")
    ward: Mapped["Ward | None"] = relationship(back_populates="supporters")
    mobilizer: Mapped["Mobilizer | None"] = relationship(back_populates="supporters")

    def __str__(self) -> str:
        return self.full_name
