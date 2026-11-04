"""The party office: settings, offices, members, aspirants and volunteers."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
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
from backend.models.enums import (
    AspirantStatus,
    ContactMethod,
    PartyConsentChannel,
    PartyMemberStatus,
    PartyRequestKind,
    PartyRoleName,
    Profession,
    Seat,
    VolunteerStatus,
)

if TYPE_CHECKING:
    from backend.models.campaign import Campaign
    from backend.models.geography import Constituency, County, RegistrationCentre, Ward
    from backend.models.user import User

HEX_DIGITS = "'0','1','2','3','4','5','6','7','8','9','a','b','c','d','e','f'"


def hex_colour(column: str) -> str:
    """A CHECK expression for `#rrggbb` that Postgres and SQLite both run."""
    digits = " AND ".join(f"lower(substr({column}, {i}, 1)) IN ({HEX_DIGITS})" for i in range(2, 8))
    return f"length({column}) = 7 AND substr({column}, 1, 1) = '#' AND {digits}"


class PartySettings(Base):
    """The party-only settings: registration, founding year, aspirant steps and how to pay."""

    __tablename__ = "party_settings"
    __table_args__ = (CheckConstraint("id = 1", name="singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=1)
    registration_number: Mapped[str] = mapped_column(
        String(40), default="", server_default=text("''")
    )
    founded_year: Mapped[str] = mapped_column(String(4), default="", server_default=text("''"))
    # The Vie with us page's steps, one per line.
    aspirant_steps: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    payment_instructions: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class PartyRole(TimestampMixin, Base):
    """A party office held by a login; (user, role) is the key."""

    __tablename__ = "party_roles"
    # Only a staff login can hold an office; the database refuses a campaign login.
    __table_args__ = (
        ForeignKeyConstraint(["user_id", "kind"], ["users.id", "users.kind"], ondelete="CASCADE"),
        CheckConstraint("kind = 'staff'", name="kind_is_staff"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    kind: Mapped[str] = mapped_column(String(8), default="staff", server_default="staff")
    role: Mapped[PartyRoleName] = mapped_column(
        choice_type(PartyRoleName, "party_role", length=30), primary_key=True
    )

    user: Mapped["User"] = relationship(back_populates="party_roles")


class PartyMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A person on the party register; most never sign in."""

    __tablename__ = "party_members"
    __table_args__ = (
        UniqueConstraint("phone", name="uq_party_members_phone"),
        CheckConstraint("length(trim(full_name)) > 0", name="full_name_not_blank"),
        CheckConstraint("consent_wording <> ''", name="consent_wording_not_empty"),
    )

    full_name: Mapped[str] = mapped_column(String(150), index=True)
    # The first name as typed on the join form; NULL for members who joined before it was asked.
    first_name: Mapped[str | None] = mapped_column(String(75), default=None)
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(254), default=None)
    ward_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("wards.id", ondelete="RESTRICT"), index=True
    )
    # The polling station; NULL for members who joined before it was asked.
    registration_centre_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("registration_centres.id", ondelete="RESTRICT"), default=None
    )
    status: Mapped[PartyMemberStatus] = mapped_column(
        choice_type(PartyMemberStatus, "party_member_status"),
        default=PartyMemberStatus.PENDING,
        index=True,
    )
    status_reason: Mapped[str | None] = mapped_column(Text, default=None)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    consent_wording: Mapped[str] = mapped_column(Text)
    consent_channel: Mapped[PartyConsentChannel] = mapped_column(
        choice_type(PartyConsentChannel, "party_consent_channel")
    )
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    withdraw_code: Mapped[str | None] = mapped_column(String(32), unique=True, default=None)

    ward: Mapped["Ward"] = relationship()
    registration_centre: Mapped["RegistrationCentre | None"] = relationship()
    volunteer: Mapped["VolunteerProfile | None"] = relationship(
        back_populates="member", uselist=False, passive_deletes=True
    )

    def __str__(self) -> str:
        return self.full_name


class PartyRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A public join or withdrawal waiting to be applied to the register; deleted once applied."""

    __tablename__ = "party_requests"
    __table_args__ = (Index("ix_party_requests_created_at", "created_at"),)

    kind: Mapped[PartyRequestKind] = mapped_column(
        choice_type(PartyRequestKind, "party_request_kind")
    )
    # A join's new withdraw code, or the code a withdrawal presents.
    code: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
        sort_order=101,
    )

    member: Mapped[PartyMember | None] = relationship(back_populates="volunteer")
    ward: Mapped["Ward"] = relationship()
    registration_centre: Mapped["RegistrationCentre | None"] = relationship()


# A member has at most one nomination in these statuses.
LIVE_NOMINATION = "status IN ('draft', 'submitted', 'approved', 'suspended')"


class Aspirant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A party member's nomination for a seat, and the campaign made for it."""

    __tablename__ = "aspirants"
    __table_args__ = (
        CheckConstraint(
            "(seat = 'mca' AND ward_id IS NOT NULL "
            "AND constituency_id IS NULL AND county_id IS NULL) "
            "OR (seat = 'mp' AND constituency_id IS NOT NULL "
            "AND ward_id IS NULL AND county_id IS NULL) "
            "OR (seat IN ('governor', 'senator', 'women_rep') AND county_id IS NOT NULL "
            "AND ward_id IS NULL AND constituency_id IS NULL)",
            name="area_matches_seat",
        ),
        UniqueConstraint("campaign_id", name="uq_aspirants_campaign_id"),
        Index(
            "uq_aspirants_one_live_per_member",
            "member_id",
            unique=True,
            sqlite_where=text(LIVE_NOMINATION),
            postgresql_where=text(LIVE_NOMINATION),
        ),
    )

    member_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("party_members.id", ondelete="RESTRICT"), index=True
    )
    seat: Mapped[Seat] = mapped_column(choice_type(Seat, "seat"), index=True)
    county_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("counties.id", ondelete="RESTRICT"), default=None
    )
    constituency_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("constituencies.id", ondelete="RESTRICT"), default=None
    )
    ward_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("wards.id", ondelete="RESTRICT"), default=None
    )
    status: Mapped[AspirantStatus] = mapped_column(
        choice_type(AspirantStatus, "aspirant_status"),
        default=AspirantStatus.DRAFT,
        index=True,
    )
    status_reason: Mapped[str | None] = mapped_column(Text, default=None)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="SET NULL"), default=None
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
        sort_order=101,
    )

    member: Mapped[PartyMember] = relationship()
    county: Mapped["County | None"] = relationship()
    constituency: Mapped["Constituency | None"] = relationship()
    ward: Mapped["Ward | None"] = relationship()
    campaign: Mapped["Campaign | None"] = relationship()
