"""A one-way announcement from the campaign's leads to a unit's team, read through the bell."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, UUIDPrimaryKeyMixin, campaign_ref, user_ref


class Announcement(UUIDPrimaryKeyMixin, Base):
    """Sent to the whole campaign, one ward, or one registration centre; each recipient gets a
    notice, and its read time is the read receipt."""

    __tablename__ = "announcements"

    campaign_id: Mapped[uuid.UUID] = campaign_ref()
    author_id: Mapped[uuid.UUID | None] = user_ref()
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text, default="")
    # Both None: the whole campaign. A centre always comes with its ward.
    ward_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("wards.id", ondelete="SET NULL"), default=None
    )
    registration_centre_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("registration_centres.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
