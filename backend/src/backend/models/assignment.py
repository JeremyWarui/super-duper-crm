"""Work given to a mobilizer or agent: what a payment is made against once it is done."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_type
from backend.models.enums import AssignmentKind, AssignmentStatus
from backend.models.event import Event
from backend.models.geography import RegistrationCentre, Ward
from backend.models.mobilizer import Mobilizer
from backend.models.team import Agent

ONE_MEMBER = "(mobilizer_id IS NULL) <> (agent_id IS NULL)"


class Assignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An event, ward work or an activity for one mobilizer or agent, with its amount.

    Its ward (and centre) is where the work is, so a coordinator's area covers it.
    """

    __tablename__ = "assignments"
    __table_args__ = (
        CheckConstraint(ONE_MEMBER, name="one_member"),
        CheckConstraint("amount_kes > 0", name="amount_kes_positive"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    mobilizer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("mobilizers.id", ondelete="CASCADE"), default=None, index=True
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("agents.id", ondelete="CASCADE"), default=None, index=True
    )
    kind: Mapped[AssignmentKind] = mapped_column(choice_type(AssignmentKind, "assignment_kind"))
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("events.id", ondelete="SET NULL"), default=None, index=True
    )
    ward_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("wards.id", ondelete="SET NULL"), default=None, index=True
    )
    registration_centre_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("registration_centres.id", ondelete="SET NULL"), default=None
    )
    description: Mapped[str] = mapped_column(Text, default="")
    amount_kes: Mapped[int] = mapped_column(Integer)
    status: Mapped[AssignmentStatus] = mapped_column(
        choice_type(AssignmentStatus, "assignment_status"), default=AssignmentStatus.ASSIGNED
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    done_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    mobilizer: Mapped[Mobilizer | None] = relationship()
    agent: Mapped[Agent | None] = relationship()
    event: Mapped[Event | None] = relationship()
    ward: Mapped[Ward | None] = relationship()
    registration_centre: Mapped[RegistrationCentre | None] = relationship()

    @property
    def label(self) -> str:
        """What the work is, as a payment shows it."""
        if self.kind is AssignmentKind.EVENT and self.event is not None:
            return self.event.title[:150]
        place = self.ward.name if self.ward is not None else ""
        if self.kind is AssignmentKind.WARD_WORK:
            return f"Ward work: {place}"[:150] if place else "Ward work"
        return (self.description or "Activity")[:150]
