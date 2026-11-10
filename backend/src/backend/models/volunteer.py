"""Volunteer profiles: a party member's (`campaign_id` NULL), or a campaign's."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    choice_type,
    updated_at_column,
)
from backend.models.enums import ContactMethod, Profession, VolunteerStatus

if TYPE_CHECKING:
    from backend.models import PartyMember
    from backend.models.geography import RegistrationCentre, Ward


class VolunteerProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A party member's volunteer profile (`campaign_id` NULL), or a campaign's volunteer."""

    __tablename__ = "volunteer_profiles"
    __table_args__ = (
        UniqueConstraint("member_id", name="uq_volunteer_profiles_member_id"),
        # A party row has a member; a campaign row has none.
        CheckConstraint("(campaign_id IS NULL) = (member_id IS NOT NULL)", name="owner"),
        CheckConstraint("consent_wording <> ''", name="consent_wording_not_empty"),
        Index(
            "uq_volunteer_profiles_party_phone",
            "phone",
            unique=True,
            postgresql_where=text("campaign_id IS NULL"),
            sqlite_where=text("campaign_id IS NULL"),
        ),
        UniqueConstraint("campaign_id", "phone", name="uq_volunteer_profiles_campaign_phone"),
        Index("ix_volunteer_profiles_campaign_id_status", "campaign_id", "status"),
    )

    member_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("party_members.id", ondelete="CASCADE"), default=None
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="CASCADE"), default=None
    )
    first_name: Mapped[str] = mapped_column(String(75))
    last_name: Mapped[str] = mapped_column(String(75))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(254), default=None)
    ward_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("wards.id", ondelete="RESTRICT"), index=True
    )
    registration_centre_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("registration_centres.id", ondelete="RESTRICT"), default=None
    )
    profession: Mapped[Profession | None] = mapped_column(
        choice_type(Profession, "profession"), default=None
    )
    profession_other: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[VolunteerStatus] = mapped_column(
        choice_type(VolunteerStatus, "volunteer_status"),
        default=VolunteerStatus.INTERESTED,
    )
    # A list of VolunteerArea values.
    interests: Mapped[list[str]] = mapped_column(JSON, default=list)
    interest_other: Mapped[str] = mapped_column(String(100), default="")
    availability_notes: Mapped[str | None] = mapped_column(Text, default=None)
    preferred_contact: Mapped[ContactMethod] = mapped_column(
        choice_type(ContactMethod, "contact_method")
    )
    consent_wording: Mapped[str] = mapped_column(Text)
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    withdraw_code: Mapped[str | None] = mapped_column(String(32), unique=True, default=None)
    # Personal fields blanked on request; the row stays for counts.
    erased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    updated_at: Mapped[datetime] = updated_at_column()

    member: Mapped["PartyMember | None"] = relationship(back_populates="volunteer")
    ward: Mapped["Ward"] = relationship()
    registration_centre: Mapped["RegistrationCentre | None"] = relationship()
