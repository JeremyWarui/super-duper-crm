"""The API token a signed-in user sends on every request."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from backend.models.user import User


class AuthToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One live token per user. Signing out deletes it.

    A Google sign-in leaves a one-time handoff (its SHA-256 here) the browser trades for the token.
    """

    __tablename__ = "auth_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    key: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    handoff_hash: Mapped[str | None] = mapped_column(String(64), unique=True, default=None)
    handoff_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    user: Mapped["User"] = relationship(back_populates="auth_token")
