"""The party's public content: leaders, news and events, county branches, and news sign-ups."""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_type
from backend.models.enums import PostKind
from backend.models.geography import County


def _updated_at() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
        sort_order=101,
    )


class PartyLeader(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A leader shown on the public Leadership page once published."""

    __tablename__ = "party_leaders"

    name: Mapped[str] = mapped_column(String(150))
    position: Mapped[str] = mapped_column(String(150))
    bio: Mapped[str] = mapped_column(Text, default="")
    photo_url: Mapped[str] = mapped_column(String(500), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = _updated_at()


class PartyPost(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A news item or a party event, shown on the public site once published."""

    __tablename__ = "party_posts"
    __table_args__ = (
        CheckConstraint("(kind = 'event') = (event_date IS NOT NULL)", name="event_has_date"),
        Index("ix_party_posts_kind_published_event_date", "kind", "published", "event_date"),
        Index("ix_party_posts_kind_published_published_on", "kind", "published", "published_on"),
    )

    kind: Mapped[PostKind] = mapped_column(choice_type(PostKind, "post_kind"))
    title: Mapped[str] = mapped_column(String(150))
    body: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str] = mapped_column(String(500), default="")
    event_date: Mapped[date | None] = mapped_column(Date, default=None)
    venue: Mapped[str] = mapped_column(String(150), default="")
    # The first day it was published; kept when it is unpublished and published again.
    published_on: Mapped[date | None] = mapped_column(Date, default=None)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = _updated_at()


class Subscriber(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A phone or email that asked for party news, with the consent it gave."""

    __tablename__ = "subscribers"
    __table_args__ = (CheckConstraint("channel IN ('sms', 'email')", name="channel"),)

    contact: Mapped[str] = mapped_column(String(254), unique=True)
    channel: Mapped[str] = mapped_column(String(10))
    consent_wording: Mapped[str] = mapped_column(Text)
    notice_version: Mapped[str] = mapped_column(String(20))
    unsubscribe_code: Mapped[str] = mapped_column(String(32), unique=True)


class Branch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A county's party branch: its officials, office and next meeting, public once published."""

    __tablename__ = "branches"

    county_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("counties.id", ondelete="CASCADE"), unique=True
    )
    chairperson: Mapped[str] = mapped_column(String(150), default="", server_default="")
    secretary: Mapped[str] = mapped_column(String(150), default="", server_default="")
    office_address: Mapped[str] = mapped_column(String(300), default="", server_default="")
    phone: Mapped[str] = mapped_column(String(20), default="", server_default="")
    email: Mapped[str] = mapped_column(String(254), default="", server_default="")
    next_meeting_on: Mapped[date | None] = mapped_column(Date, default=None)
    next_meeting_venue: Mapped[str] = mapped_column(String(150), default="", server_default="")
    published: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    updated_at: Mapped[datetime] = _updated_at()

    county: Mapped["County"] = relationship(lazy="raise")


class HeroSlide(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One slide of the homepage carousel, shown once published; at most five exist."""

    __tablename__ = "hero_slides"

    image_url: Mapped[str] = mapped_column(String(500), default="", server_default="")
    kicker: Mapped[str] = mapped_column(String(80), default="", server_default="")
    headline: Mapped[str] = mapped_column(String(120))
    line: Mapped[str] = mapped_column(String(300), default="", server_default="")
    button_label: Mapped[str] = mapped_column(String(40), default="", server_default="")
    button_url: Mapped[str] = mapped_column(String(500), default="", server_default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    published: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    updated_at: Mapped[datetime] = _updated_at()


class AgendaIssue(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One issue of the party's agenda, on the homepage and its own page once published."""

    __tablename__ = "agenda_issues"

    title: Mapped[str] = mapped_column(String(150))
    summary: Mapped[str] = mapped_column(String(300), default="", server_default="")
    what_we_will_do: Mapped[str] = mapped_column(Text, default="", server_default="")
    why_it_matters: Mapped[str] = mapped_column(Text, default="", server_default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    published: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    updated_at: Mapped[datetime] = _updated_at()
