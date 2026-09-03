"""The single login model, ported from Django's `AbstractUser`.

Dropped along with Django: `is_staff`, `groups`, and `user_permissions`. All
three existed to drive `django.contrib.admin` and `django.contrib.auth`'s
permission tables, neither of which survives the move. `role` is the
authorization signal this application actually uses.

Kept: `password` is stored as `password_hash` under its real name. Hashing is
not wired up here because no auth code exists yet; the column is the contract.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_type
from backend.models.enums import UserRole

if TYPE_CHECKING:
    from backend.models.campaign import Campaign
    from backend.models.mobilizer import Mobilizer


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(254), default="")
    first_name: Mapped[str] = mapped_column(String(150), default="")
    last_name: Mapped[str] = mapped_column(String(150), default="")
    phone: Mapped[str] = mapped_column(String(20), default="")

    role: Mapped[UserRole] = mapped_column(
        choice_type(UserRole, "user_role"),
        default=UserRole.MANAGER,
    )

    password_hash: Mapped[str] = mapped_column(String(128), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    campaigns: Mapped[list["Campaign"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    mobilizer_profile: Mapped["Mobilizer | None"] = relationship(back_populates="user")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self) -> str:
        return f"{self.full_name or self.username} ({self.role.label})"
