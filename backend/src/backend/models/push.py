"""A browser or installed app that agreed to show this login's call alerts."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, UUIDPrimaryKeyMixin, user_ref


class PushSubscription(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "push_subscriptions"

    user_id: Mapped[uuid.UUID | None] = user_ref()
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(String(200))
    auth: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
