"""Anyone who signs in: candidate, campaign manager, or mobilizer."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_type
from backend.models.enums import UserRole

if TYPE_CHECKING:
    from backend.models.auth_token import AuthToken
    from backend.models.membership import CampaignMember
    from backend.models.mobilizer import Mobilizer


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(254), default="")
    first_name: Mapped[str] = mapped_column(String(150), default="")
    last_name: Mapped[str] = mapped_column(String(150), default="")
    phone: Mapped[str] = mapped_column(String(20), default="")

    # What this user is allowed to do.
    role: Mapped[UserRole] = mapped_column(
        choice_type(UserRole, "user_role"),
        default=UserRole.MANAGER,
    )

    # Hashing is added with the auth code; this column is the place for it.
    password_hash: Mapped[str] = mapped_column(String(128), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    # Every campaign this user works on, in any capacity, including the ones they
    # stand in as the candidate. What scoping reads.
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

    def __str__(self) -> str:
        return f"{self.full_name or self.username} ({self.role.label})"


def member_refusal(named: "User") -> str | None:
    """Why this login may not be put on a campaign, or None if it may.

    One rule in one place: `api.scope.add_member` builds a team from inside a
    campaign and `services.admin.add_member` does it from the console, and the
    two must not drift. It lives here because those two do not import each
    other, and both already import this.
    """
    if named.is_superuser:
        return (
            "A superuser reaches every campaign through the console, and would lose the "
            "campaign app by being put on one."
        )
    if not named.is_active:
        return f"{named.username} is disabled, so they could not sign in to work on it."
    return None
