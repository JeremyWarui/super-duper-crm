"""People who sign themselves up to a workspace's team, and its polling agents."""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    campaign_ref,
    choice_type,
    partial_unique,
    user_ref,
)
from backend.models.enums import AgentStatus, FieldRole, RegistrationStatus
from backend.models.geography import RegistrationCentre, Ward
from backend.models.user import User

STILL_COUNTS = "status != 'rejected'"


class TeamRegistration(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A mobilizer or agent who signed up on the team link, with the pending login it made.

    Phone and ID number are unique per workspace among registrations not rejected. Rejection
    deletes the login and blanks the ID number.
    """

    __tablename__ = "team_registrations"
    __table_args__ = (
        partial_unique(
            "uq_team_registrations_campaign_phone",
            "campaign_id",
            "phone",
            where=STILL_COUNTS,
        ),
        partial_unique(
            "uq_team_registrations_campaign_id_number",
            "campaign_id",
            "id_number",
            where=STILL_COUNTS,
        ),
    )

    campaign_id: Mapped[uuid.UUID] = campaign_ref()
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), default=None, unique=True
    )
    role: Mapped[FieldRole] = mapped_column(choice_type(FieldRole, "field_role"))
    first_name: Mapped[str] = mapped_column(String(150))
    last_name: Mapped[str] = mapped_column(String(150), default="")
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str] = mapped_column(String(254))
    id_number: Mapped[str] = mapped_column(String(20))
    ward_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("wards.id", ondelete="SET NULL"), default=None
    )
    registration_centre_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("registration_centres.id", ondelete="SET NULL"), default=None
    )
    consent_wording: Mapped[str] = mapped_column(Text)
    consent_version: Mapped[str] = mapped_column(String(20))
    status: Mapped[RegistrationStatus] = mapped_column(
        choice_type(RegistrationStatus, "registration_status"), default=RegistrationStatus.PENDING
    )
    decided_by_id: Mapped[uuid.UUID | None] = user_ref()
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    reason: Mapped[str] = mapped_column(Text, default="")
    # Personal fields and the ID number blanked on request, once the person is off the team.
    erased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    ward: Mapped[Ward | None] = relationship()
    registration_centre: Mapped[RegistrationCentre | None] = relationship()

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class Agent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A polling agent on a workspace, readied for one registration centre."""

    __tablename__ = "agents"

    campaign_id: Mapped[uuid.UUID] = campaign_ref()
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    ward_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("wards.id", ondelete="SET NULL"), default=None, index=True
    )
    registration_centre_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("registration_centres.id", ondelete="SET NULL"), default=None, index=True
    )
    status: Mapped[AgentStatus] = mapped_column(
        choice_type(AgentStatus, "agent_status"), default=AgentStatus.APPLIED
    )
    training_date: Mapped[date | None] = mapped_column(Date, default=None)

    user: Mapped[User] = relationship()
    ward: Mapped[Ward | None] = relationship()
    registration_centre: Mapped[RegistrationCentre | None] = relationship()
