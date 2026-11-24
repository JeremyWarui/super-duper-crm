"""A note to one login about something that changed for them, shown under the bell."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, UUIDPrimaryKeyMixin, campaign_ref


class Notice(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "notices"

    campaign_id: Mapped[uuid.UUID] = campaign_ref()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    text: Mapped[str] = mapped_column(String(300))
    # A first line of what it is about, shown under the text.
    detail: Mapped[str] = mapped_column(Text, default="", server_default="")
    # Who caused it, when someone did.
    sender_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    # The page the note opens, inside the app.
    url: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # Set when the notice delivers an announcement; its read time is the read receipt.
    announcement_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("announcements.id", ondelete="CASCADE"), default=None, index=True
    )
