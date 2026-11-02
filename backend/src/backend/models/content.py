"""The party's public content: its leaders, and its news and events."""

from datetime import UTC, date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_type
from backend.models.enums import PostKind


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
