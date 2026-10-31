"""The party's public identity: one row, id 1."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_type
from backend.models.enums import (
    PartyConsentChannel,
    PartyMemberStatus,
    PartyRequestKind,
    PartyRoleName,
)

if TYPE_CHECKING:
    from backend.models.geography import Ward
    from backend.models.user import User

HEX_DIGITS = "'0','1','2','3','4','5','6','7','8','9','a','b','c','d','e','f'"


def hex_colour(column: str) -> str:
    """A CHECK expression for `#rrggbb` that Postgres and SQLite both run."""
    digits = " AND ".join(f"lower(substr({column}, {i}, 1)) IN ({HEX_DIGITS})" for i in range(2, 8))
    return f"length({column}) = 7 AND substr({column}, 1, 1) = '#' AND {digits}"


class PartySettings(Base):
    """Name, branding, contacts and manifesto of the party this deployment serves."""

    __tablename__ = "party_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="singleton"),
        CheckConstraint(hex_colour("primary_colour"), name="primary_colour_hex"),
        CheckConstraint(hex_colour("secondary_colour"), name="secondary_colour_hex"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=1)
    name: Mapped[str] = mapped_column(String(150))
    short_name: Mapped[str] = mapped_column(String(30), default="")
    logo_url: Mapped[str] = mapped_column(String(500), default="")
    primary_colour: Mapped[str] = mapped_column(String(7), default="#1f2937")
    secondary_colour: Mapped[str] = mapped_column(String(7), default="#f59e0b")
    contact_email: Mapped[str] = mapped_column(String(254), default="")
    contact_phone: Mapped[str] = mapped_column(String(20), default="")
    address: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    manifesto_text: Mapped[str] = mapped_column(Text, default="")
    manifesto_url: Mapped[str] = mapped_column(String(500), default="")
    social_links: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class PartyRole(TimestampMixin, Base):
    """A party office held by a login; (user, role) is the key."""

    __tablename__ = "party_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
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
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(254), default=None)
    ward_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("wards.id", ondelete="RESTRICT"), index=True
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
