"""A ground organizer working a ward, and optionally one registration centre."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from backend.models.campaign import Campaign
    from backend.models.event import Event
    from backend.models.geography import RegistrationCentre, Ward
    from backend.models.supporter import Supporter
    from backend.models.user import User


class Mobilizer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One per unit of a campaign: a ward, or a registration centre in a ward race."""

    __tablename__ = "mobilizers"
    __table_args__ = (
        Index(
            "uq_mobilizers_campaign_ward",
            "campaign_id",
            "ward_id",
            unique=True,
            postgresql_where=text("ward_id IS NOT NULL AND registration_centre_id IS NULL"),
            sqlite_where=text("ward_id IS NOT NULL AND registration_centre_id IS NULL"),
        ),
        Index(
            "uq_mobilizers_campaign_registration_centre",
            "campaign_id",
            "registration_centre_id",
            unique=True,
            postgresql_where=text("registration_centre_id IS NOT NULL"),
            sqlite_where=text("registration_centre_id IS NOT NULL"),
        ),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    # None until assigned.
    ward_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("wards.id", ondelete="CASCADE"), default=None, index=True
    )
    registration_centre_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("registration_centres.id", ondelete="SET NULL"),
        default=None,
        index=True,
    )

    # Optional login; deleting it keeps the row.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), default=None, unique=True
    )

    full_name: Mapped[str] = mapped_column(String(150))
    phone: Mapped[str] = mapped_column(String(20), default="")

    campaign: Mapped["Campaign"] = relationship(back_populates="mobilizers")
    ward: Mapped["Ward | None"] = relationship(back_populates="mobilizers")
    registration_centre: Mapped["RegistrationCentre | None"] = relationship(
        back_populates="mobilizers"
    )
    user: Mapped["User | None"] = relationship(back_populates="mobilizer_profile")

    events: Mapped[list["Event"]] = relationship(back_populates="mobilizer")
    supporters: Mapped[list["Supporter"]] = relationship(back_populates="mobilizer")

    def __str__(self) -> str:
        return f"{self.full_name} - {self.ward.name if self.ward else 'no ward'}"
