"""Anyone who signs in: the campaign's team, and superusers."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    choice_type,
    partial_unique,
    starts_false,
)
from backend.models.enums import UserRole

if TYPE_CHECKING:
    from backend.models.auth_token import AuthToken
    from backend.models.membership import CampaignMember
    from backend.models.mobilizer import Mobilizer


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    # Target of campaign_members' (user_id, role) foreign key.
    __table_args__ = (
        UniqueConstraint("id", "role"),
        CheckConstraint("NOT (pending AND is_active)", name="pending_is_inactive"),
        # The sign-in name; stored lower-cased.
        partial_unique(
            "uq_users_email",
            "email",
            where="email <> ''",
        ),
    )

    username: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(254), default="")
    first_name: Mapped[str] = mapped_column(String(150), default="")
    last_name: Mapped[str] = mapped_column(String(150), default="")
    phone: Mapped[str] = mapped_column(String(20), default="")

    role: Mapped[UserRole | None] = mapped_column(choice_type(UserRole, "user_role"), default=None)

    password_hash: Mapped[str] = mapped_column(String(128), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Registered by the person and awaiting approval; inactive until approved.
    pending: Mapped[bool] = starts_false()
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    memberships: Mapped[list["CampaignMember"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    mobilizer_profile: Mapped["Mobilizer | None"] = relationship(back_populates="user")
    auth_token: Mapped["AuthToken | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def display_name(self) -> str:
        """The full name, or the username when no name is set."""
        return self.full_name or self.username

    def __str__(self) -> str:
        role = self.role.label if self.role else "no campaign role"
        return f"{self.display_name} ({role})"
