"""The party's public identity: one row, id 1."""

from datetime import UTC, datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base

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
