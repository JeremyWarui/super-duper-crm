"""The website's identity and the organisation type: one row, id 1."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_type
from backend.models.enums import OrganisationType
from backend.models.party import hex_colour


class SiteSettings(Base):
    """Name, branding, contacts, manifesto and privacy notice, shared by every organisation type."""

    __tablename__ = "site_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="singleton"),
        CheckConstraint(hex_colour("primary_colour"), name="primary_colour_hex"),
        CheckConstraint(hex_colour("secondary_colour"), name="secondary_colour_hex"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=1)
    # Written once at setup; no schema, screen or command changes it.
    organisation_type: Mapped[OrganisationType] = mapped_column(
        choice_type(OrganisationType, "organisation_type")
    )
    name: Mapped[str] = mapped_column(String(150))
    short_name: Mapped[str] = mapped_column(String(30), default="")
    slogan: Mapped[str] = mapped_column(String(150), default="", server_default=text("''"))
    about_headline: Mapped[str] = mapped_column(String(150), default="", server_default=text("''"))
    logo_url: Mapped[str] = mapped_column(String(500), default="")
    logo_file_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("stored_files.id", ondelete="SET NULL"), default=None
    )
    primary_colour: Mapped[str] = mapped_column(String(7), default="#1f2937")
    secondary_colour: Mapped[str] = mapped_column(String(7), default="#f59e0b")
    contact_email: Mapped[str] = mapped_column(String(254), default="")
    contact_phone: Mapped[str] = mapped_column(String(20), default="")
    address: Mapped[str] = mapped_column(String(300), default="")
    social_links: Mapped[dict] = mapped_column(JSON, default=dict)
    description: Mapped[str] = mapped_column(Text, default="")
    manifesto_text: Mapped[str] = mapped_column(Text, default="")
    manifesto_url: Mapped[str] = mapped_column(String(500), default="")
    privacy_notice: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    # How to give, shown on the Contribute page; the site takes no money itself.
    payment_instructions: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    # Recorded with every news sign-up; raised when the notice changes.
    privacy_notice_version: Mapped[str] = mapped_column(
        String(20), default="1", server_default=text("'1'")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class SetupToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A one-time token that opens the first-run setup; only its SHA-256 is stored."""

    __tablename__ = "setup_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
