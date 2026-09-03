"""Ground organizer, assigned to a ward (and optionally a registration centre)."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from backend.models.campaign import Campaign
    from backend.models.event import Event
    from backend.models.geography import RegistrationCentre, Ward
    from backend.models.supporter import Supporter
    from backend.models.user import User


class Mobilizer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mobilizers"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    ward_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("wards.id", ondelete="CASCADE"), index=True
    )
    registration_centre_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("registration_centres.id", ondelete="SET NULL"),
        default=None,
        index=True,
    )

    # Optional login: a mobilizer may report through the app, or not.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), default=None, unique=True
    )

    full_name: Mapped[str] = mapped_column(String(150))
    phone: Mapped[str] = mapped_column(String(20), default="")

    campaign: Mapped["Campaign"] = relationship(back_populates="mobilizers")
    ward: Mapped["Ward"] = relationship(back_populates="mobilizers")
    registration_centre: Mapped["RegistrationCentre | None"] = relationship(
        back_populates="mobilizers"
    )
    user: Mapped["User | None"] = relationship(back_populates="mobilizer_profile")

    events: Mapped[list["Event"]] = relationship(back_populates="mobilizer")
    supporters: Mapped[list["Supporter"]] = relationship(back_populates="mobilizer")

    # One per ward to start. The Django model left this open on purpose; add a
    # unique constraint on (campaign_id, ward_id) if you decide to enforce it.

    def __str__(self) -> str:
        return f"{self.full_name} - {self.ward.name}"
