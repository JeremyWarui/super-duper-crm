"""Online meetings: a LiveKit room the campaign joins by audio or video, and who was in it."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, UUIDPrimaryKeyMixin, campaign_ref, user_ref


class Meeting(UUIDPrimaryKeyMixin, Base):
    """One call, from Start to End."""

    __tablename__ = "meetings"

    campaign_id: Mapped[uuid.UUID] = campaign_ref()
    title: Mapped[str] = mapped_column(String(150))
    # "audio" or "video"; an audio meeting lets nobody publish a camera.
    mode: Mapped[str] = mapped_column(String(10))
    host_id: Mapped[uuid.UUID | None] = user_ref()
    # Invited the whole campaign when None; a centre comes with its ward.
    ward_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("wards.id", ondelete="SET NULL"), default=None
    )
    registration_centre_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("registration_centres.id", ondelete="SET NULL"), default=None
    )
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("events.id", ondelete="SET NULL"), default=None
    )
    livekit_room: Mapped[str] = mapped_column(String(64), unique=True)
    # "live" or "ended".
    status: Mapped[str] = mapped_column(String(10), default="live")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class MeetingAttendance(UUIDPrimaryKeyMixin, Base):
    """One stay in a meeting, from joining to leaving; rejoining starts another."""

    __tablename__ = "meeting_attendance"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("meetings.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID | None] = user_ref()
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
