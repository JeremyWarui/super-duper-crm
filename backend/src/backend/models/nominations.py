"""Nomination windows the party publishes, and the documents a member's application carries."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    choice_type,
    updated_at_column,
)
from backend.models.enums import Seat


class NominationWindow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A timetable: the seats open, the dates applications are taken, and the requirements.

    The Nominations Officer drafts it; the Party Super Admin, someone else, publishes it.
    """

    __tablename__ = "nomination_windows"

    title: Mapped[str] = mapped_column(String(150))
    opens_on: Mapped[date] = mapped_column(Date)
    closes_on: Mapped[date] = mapped_column(Date)
    requirements: Mapped[str] = mapped_column(Text, default="")
    # draft or published.
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    drafted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    published_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    updated_at: Mapped[datetime] = updated_at_column()

    seats: Mapped[list["NominationSeat"]] = relationship(
        back_populates="window",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="NominationSeat.seat",
    )


class NominationSeat(UUIDPrimaryKeyMixin, Base):
    """A seat open in a window, with its nomination fee; 0 means no fee."""

    __tablename__ = "nomination_seats"
    __table_args__ = (
        UniqueConstraint("window_id", "seat", name="uq_nomination_seats_window_seat"),
    )

    window_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("nomination_windows.id", ondelete="CASCADE"), index=True
    )
    seat: Mapped[Seat] = mapped_column(choice_type(Seat, "seat"))
    fee_kes: Mapped[int] = mapped_column(Integer, default=0)

    window: Mapped[NominationWindow] = relationship(back_populates="seats")


class AspirantDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A document a member attached to their application, kept as a private upload."""

    __tablename__ = "aspirant_documents"

    aspirant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("aspirants.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(100))
    file_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("stored_files.id", ondelete="RESTRICT")
    )
