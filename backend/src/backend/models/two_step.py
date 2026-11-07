"""2-step sign-in: each login's authenticator app secret and recovery codes."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, TimestampMixin


class UserTotp(TimestampMixin, Base):
    """A login's TOTP secret, encrypted with SECRET_KEY; on once `confirmed_at` is set.

    `last_step` is the last 30-second step a code was accepted for, so a code works once.
    `recovery_hashes` holds the SHA-256 of each unused recovery code.
    """

    __tablename__ = "user_totp"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    secret: Mapped[str] = mapped_column(Text)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_step: Mapped[int] = mapped_column(Integer, default=0)
    recovery_hashes: Mapped[list] = mapped_column(JSON, default=list)
