"""The API token a signed-in user sends on every request."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from backend.models.user import User


class AuthToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One live token per user. Signing out deletes it."""

    __tablename__ = "auth_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    key: Mapped[str] = mapped_column(String(40), unique=True, index=True)

    user: Mapped["User"] = relationship(back_populates="auth_token")
