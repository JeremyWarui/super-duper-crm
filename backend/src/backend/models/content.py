"""The party's public content: leaders, news and events, county branches, and news sign-ups."""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    Uuid,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_type
from backend.models.enums import PostKind, PostLabel, Seat
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
    photo_file_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("stored_files.id", ondelete="SET NULL"), default=None
    )
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
    image_file_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("stored_files.id", ondelete="SET NULL"), default=None
    )
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


class PartyDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A party document linked from the About page once published, such as the constitution."""

    __tablename__ = "party_documents"

    title: Mapped[str] = mapped_column(String(150))
    url: Mapped[str] = mapped_column(String(500))
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("stored_files.id", ondelete="SET NULL"), default=None
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    published: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    updated_at: Mapped[datetime] = _updated_at()


class PartyValue(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One of the party's values, under What we believe on the About page once published."""

    __tablename__ = "party_values"

    title: Mapped[str] = mapped_column(String(150))
    text: Mapped[str] = mapped_column(String(300), default="", server_default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    published: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    updated_at: Mapped[datetime] = _updated_at()


class PartyOrgan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A party organ, under How the party is run on the About page once published."""

    __tablename__ = "party_organs"

    title: Mapped[str] = mapped_column(String(150))
    text: Mapped[str] = mapped_column(String(300), default="", server_default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    published: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    updated_at: Mapped[datetime] = _updated_at()


class PrimaryResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One candidate's votes in a party primary, on the Results page once published."""

    __tablename__ = "primary_results"
    __table_args__ = (CheckConstraint("votes >= 0", name="votes_not_negative"),)

    seat: Mapped[Seat] = mapped_column(choice_type(Seat, "seat"))
    area: Mapped[str] = mapped_column(String(150))
    candidate: Mapped[str] = mapped_column(String(150))
    votes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    declared_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Set by the demo seed; the page then says the results are demo results.
    demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    published: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    updated_at: Mapped[datetime] = _updated_at()


class PartyVideo(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A video in the homepage's Watch row once published; it links out to where it is hosted."""

    __tablename__ = "party_videos"

    title: Mapped[str] = mapped_column(String(150))
    url: Mapped[str] = mapped_column(String(500))
    # Empty means the page takes YouTube's thumbnail for a YouTube link.
    thumbnail_url: Mapped[str] = mapped_column(String(500), default="", server_default="")
    duration: Mapped[str] = mapped_column(String(8), default="", server_default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    published: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    updated_at: Mapped[datetime] = _updated_at()


# The aspirants a party event names; it shows on each one's candidate profile.
party_post_aspirants = Table(
    "party_post_aspirants",
    Base.metadata,
    Column("post_id", Uuid, ForeignKey("party_posts.id", ondelete="CASCADE"), primary_key=True),
    Column("aspirant_id", Uuid, ForeignKey("aspirants.id", ondelete="CASCADE"), primary_key=True),
)


class CandidateProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A campaign's candidate page on the website; a hosted campaign's names its aspirant."""

    __tablename__ = "candidate_profiles"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="CASCADE"), unique=True
    )
    aspirant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("aspirants.id", ondelete="CASCADE"), unique=True, default=None
    )
    photo_url: Mapped[str] = mapped_column(String(500), default="", server_default="")
    photo_file_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("stored_files.id", ondelete="SET NULL"), default=None
    )
    slogan: Mapped[str] = mapped_column(String(120), default="", server_default="")
    bio: Mapped[str] = mapped_column(Text, default="", server_default="")
    # Up to three {"title", "text"} pairs.
    priorities: Mapped[list[dict]] = mapped_column(JSON, default=list)
    office_address: Mapped[str] = mapped_column(String(300), default="", server_default="")
    office_phone: Mapped[str] = mapped_column(String(20), default="", server_default="")
    office_email: Mapped[str] = mapped_column(String(254), default="", server_default="")
    published: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    updated_at: Mapped[datetime] = _updated_at()
