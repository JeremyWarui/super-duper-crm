"""One-time sign-in links and the email the app sends."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_type
from backend.models.enums import LinkPurpose


class LoginInvite(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A link that sets a login's password once: an invite for a new login, or a reset.

    Only the token's SHA-256 is stored; the token itself is in the link alone.
    """

    __tablename__ = "login_invites"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[LinkPurpose] = mapped_column(choice_type(LinkPurpose, "link_purpose"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class EmailLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Every email the app sends, or would have sent in practice mode.

    `status` is `practice` (nothing sent), `sent` or `failed`, with the reason in `detail`.
    """

    __tablename__ = "email_log"

    to: Mapped[str] = mapped_column(String(254), index=True)
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    detail: Mapped[str] = mapped_column(Text, default="")
