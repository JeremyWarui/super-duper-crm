"""Meeting or rally, with mobilization counts."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, UUIDPrimaryKeyMixin, choice_type
from backend.models.enums import EventStatus

if TYPE_CHECKING:
    from backend.models.campaign import Campaign
    from backend.models.geography import RegistrationCentre, Ward
    from backend.models.mobilizer import Mobilizer


class Event(UUIDPrimaryKeyMixin, Base):
    """Default ordering was `-scheduled_date`."""

    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("number_reached >= 0", name="number_reached_non_negative"),
        CheckConstraint("number_attended >= 0", name="number_attended_non_negative"),
    )

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
    mobilizer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("mobilizers.id", ondelete="SET NULL"), default=None, index=True
    )

    title: Mapped[str] = mapped_column(String(150), default="")
    venue: Mapped[str] = mapped_column(String(150), default="")
    scheduled_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, index=True
    )
    status: Mapped[EventStatus] = mapped_column(
        choice_type(EventStatus, "event_status"), default=EventStatus.PLANNED
    )
    number_reached: Mapped[int] = mapped_column(Integer, default=0)
    number_attended: Mapped[int] = mapped_column(Integer, default=0)

    campaign: Mapped["Campaign"] = relationship(back_populates="events")
    ward: Mapped["Ward"] = relationship(back_populates="events")
    registration_centre: Mapped["RegistrationCentre | None"] = relationship(back_populates="events")
    mobilizer: Mapped["Mobilizer | None"] = relationship(back_populates="events")

    def __str__(self) -> str:
        return self.title or f"Event in {self.ward.name}"

    @property
    def turnout_pct(self) -> float:
        """Attendance against how many were reached to invite them."""
        if not self.number_reached:
            return 0.0
        return round(self.number_attended / self.number_reached * 100, 1)
