"""The website's content: posts, homepage items, the candidate page, and news sign-ups."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    choice_type,
    file_ref,
    starts_false,
    updated_at_column,
)
from backend.models.enums import PostKind, PostLabel
from backend.models.geography import County


class Listed:
    """An ordered content row the editor publishes: its place in the list, whether it shows, and
    when it last changed."""

    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    published: Mapped[bool] = starts_false()
    updated_at: Mapped[datetime] = updated_at_column()


class Post(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A news item or an event, shown on the public site once published."""

    __tablename__ = "posts"
    __table_args__ = (
        CheckConstraint("(kind = 'event') = (event_date IS NOT NULL)", name="event_has_date"),
        Index("ix_posts_kind_published_event_date", "kind", "published", "event_date"),
        Index("ix_posts_kind_published_published_on", "kind", "published", "published_on"),
    )

    kind: Mapped[PostKind] = mapped_column(choice_type(PostKind, "post_kind"))
    title: Mapped[str] = mapped_column(String(150))
    body: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str] = mapped_column(String(500), default="")
    event_date: Mapped[date | None] = mapped_column(Date, default=None)
    venue: Mapped[str] = mapped_column(String(150), default="")
    label: Mapped[PostLabel] = mapped_column(
        choice_type(PostLabel, "post_label"), default=PostLabel.NEWS, server_default="news"
    )
    place: Mapped[str] = mapped_column(String(80), default="", server_default="")
    author: Mapped[str] = mapped_column(String(150), default="", server_default="")
    author_photo_url: Mapped[str] = mapped_column(String(500), default="", server_default="")
    reference: Mapped[str] = mapped_column(String(40), default="", server_default="")
    pdf_url: Mapped[str] = mapped_column(String(500), default="", server_default="")
    county_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("counties.id", ondelete="SET NULL"), default=None
    )
    county: Mapped["County | None"] = relationship(lazy="raise")
    # The first day it was published; kept when it is unpublished and published again.
    published_on: Mapped[date | None] = mapped_column(Date, default=None)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = updated_at_column()


class Subscriber(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A phone or email that asked for news, with the consent it gave."""

    __tablename__ = "subscribers"
    __table_args__ = (CheckConstraint("channel IN ('sms', 'email')", name="channel"),)

    contact: Mapped[str] = mapped_column(String(254), unique=True)
    channel: Mapped[str] = mapped_column(String(10))
    consent_wording: Mapped[str] = mapped_column(Text)
    notice_version: Mapped[str] = mapped_column(String(20))
    unsubscribe_code: Mapped[str] = mapped_column(String(32), unique=True)


class HeroSlide(Listed, UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One slide of the homepage carousel, shown once published; at most five exist."""

    __tablename__ = "hero_slides"

    image_url: Mapped[str] = mapped_column(String(500), default="", server_default="")
    image_file_id: Mapped[uuid.UUID | None] = file_ref()
    kicker: Mapped[str] = mapped_column(String(80), default="", server_default="")
    headline: Mapped[str] = mapped_column(String(120))
    line: Mapped[str] = mapped_column(String(300), default="", server_default="")
    button_label: Mapped[str] = mapped_column(String(40), default="", server_default="")
    button_url: Mapped[str] = mapped_column(String(500), default="", server_default="")


class AgendaIssue(Listed, UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One issue of the agenda, on the homepage and its own page once published."""

    __tablename__ = "agenda_issues"

    title: Mapped[str] = mapped_column(String(150))
    summary: Mapped[str] = mapped_column(String(300), default="", server_default="")
    what_we_will_do: Mapped[str] = mapped_column(Text, default="", server_default="")
    why_it_matters: Mapped[str] = mapped_column(Text, default="", server_default="")
    image_url: Mapped[str] = mapped_column(String(500), default="", server_default="")


class Document(Listed, UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A document linked from the website once published, such as the manifesto."""

    __tablename__ = "documents"

    title: Mapped[str] = mapped_column(String(150))
    url: Mapped[str] = mapped_column(String(500))
    file_id: Mapped[uuid.UUID | None] = file_ref()


class Video(Listed, UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A video in the homepage's Watch row once published; it links out to where it plays."""

    __tablename__ = "videos"

    title: Mapped[str] = mapped_column(String(150))
    url: Mapped[str] = mapped_column(String(500))
    # Empty means the page takes YouTube's thumbnail for a YouTube link.
    thumbnail_url: Mapped[str] = mapped_column(String(500), default="", server_default="")
    duration: Mapped[str] = mapped_column(String(8), default="", server_default="")


class CandidateProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The campaign's candidate page, the website's homepage once published."""

    __tablename__ = "candidate_profiles"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="CASCADE"), unique=True
    )
    photo_url: Mapped[str] = mapped_column(String(500), default="", server_default="")
    photo_file_id: Mapped[uuid.UUID | None] = file_ref()
    slogan: Mapped[str] = mapped_column(String(120), default="", server_default="")
    bio: Mapped[str] = mapped_column(Text, default="", server_default="")
    # Up to three {"title", "text"} pairs.
    priorities: Mapped[list[dict]] = mapped_column(JSON, default=list)
    office_address: Mapped[str] = mapped_column(String(300), default="", server_default="")
    office_phone: Mapped[str] = mapped_column(String(20), default="", server_default="")
    office_email: Mapped[str] = mapped_column(String(254), default="", server_default="")
    published: Mapped[bool] = starts_false()
    updated_at: Mapped[datetime] = updated_at_column()
