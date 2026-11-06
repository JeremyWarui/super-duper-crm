"""The party office: settings, offices, members and aspirants."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
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
    PartyConsentChannel,
    PartyMemberStatus,
    PartyRequestKind,
    PartyRoleName,
    Seat,
)

if TYPE_CHECKING:
    from backend.models.campaign import Campaign
    from backend.models.geography import Constituency, County, RegistrationCentre, Ward
    from backend.models.nominations import AspirantDocument, NominationWindow
    from backend.models.user import User
    from backend.models.volunteer import VolunteerProfile

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
    # The party workspace coordinator whose recruitment link brought the application, and the
    # county of the applicant's ward then.
    recruited_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("campaign_members.id", ondelete="SET NULL"), default=None, index=True
    )
    recruitment_county_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("counties.id", ondelete="SET NULL"), default=None
    )

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


class RecruitmentCode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A party workspace coordinator's link to the Join the Party form; one active each."""

    __tablename__ = "recruitment_codes"
    __table_args__ = (
        Index(
            "uq_recruitment_codes_one_active",
            "campaign_member_id",
            unique=True,
            postgresql_where=text("active"),
            sqlite_where=text("active"),
        ),
    )

    campaign_member_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("campaign_members.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(16), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


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
    # A member's own application: the window it was made in, and what it declared and paid.
    window_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("nomination_windows.id", ondelete="SET NULL"), default=None
    )
    fee_kes: Mapped[int] = mapped_column(Integer, default=0)
    fee_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    fee_reference: Mapped[str] = mapped_column(String(50), default="")
    fee_marked_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    declared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
        sort_order=101,
    )

    member: Mapped[PartyMember] = relationship()
    window: Mapped["NominationWindow | None"] = relationship()
    documents: Mapped[list["AspirantDocument"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="AspirantDocument.created_at"
    )
    county: Mapped["County | None"] = relationship()
    constituency: Mapped["Constituency | None"] = relationship()
    ward: Mapped["Ward | None"] = relationship()
    campaign: Mapped["Campaign | None"] = relationship()
