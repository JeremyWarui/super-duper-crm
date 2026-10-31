"""Anyone who signs in: candidate, campaign manager, or mobilizer."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_type
from backend.models.enums import UserKind, UserRole

if TYPE_CHECKING:
    from backend.models.auth_token import AuthToken
    from backend.models.membership import CampaignMember
    from backend.models.mobilizer import Mobilizer
    from backend.models.party import PartyMember, PartyRole


def _kind_from_role(context) -> UserKind:  # type: ignore[no-untyped-def]
    return (
        UserKind.STAFF
        if context.get_current_parameters().get("role") is None
        else UserKind.CAMPAIGN
    )


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    # Targets of campaign_members' (user_id, role) and party_roles' (user_id, kind) foreign keys.
    __table_args__ = (
        UniqueConstraint("id", "role"),
        UniqueConstraint("id", "kind"),
        CheckConstraint("(kind = 'staff') = (role IS NULL)", name="kind_matches_role"),
    )

    username: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(254), default="")
    first_name: Mapped[str] = mapped_column(String(150), default="")
    last_name: Mapped[str] = mapped_column(String(150), default="")
    phone: Mapped[str] = mapped_column(String(20), default="")

    role: Mapped[UserRole | None] = mapped_column(choice_type(UserRole, "user_role"), default=None)
    kind: Mapped[UserKind] = mapped_column(
        choice_type(UserKind, "user_kind", length=8), default=_kind_from_role
    )
    # The party member this login belongs to; a member may have a staff and a candidate login.
    party_member_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("party_members.id", ondelete="SET NULL", use_alter=True),
        default=None,
    )

    password_hash: Mapped[str] = mapped_column(String(128), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    memberships: Mapped[list["CampaignMember"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    mobilizer_profile: Mapped["Mobilizer | None"] = relationship(back_populates="user")
    auth_token: Mapped["AuthToken | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )

    party_roles: Mapped[list["PartyRole"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    party_member: Mapped["PartyMember | None"] = relationship(foreign_keys=[party_member_id])

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self) -> str:
        role = self.role.label if self.role else "no campaign role"
        return f"{self.full_name or self.username} ({role})"
