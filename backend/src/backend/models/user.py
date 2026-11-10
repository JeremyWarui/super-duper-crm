"""Anyone who signs in: campaign logins, party staff, and party members."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    false,
    text,
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
        CheckConstraint("(kind = 'campaign') = (role IS NOT NULL)", name="kind_matches_role"),
        CheckConstraint("NOT (pending AND is_active)", name="pending_is_inactive"),
        # The sign-in name; stored lower-cased.
        Index(
            "uq_users_email",
            "email",
            unique=True,
            postgresql_where=text("email <> ''"),
            sqlite_where=text("email <> ''"),
        ),
        Index(
            "uq_users_member_login",
            "party_member_id",
            unique=True,
            postgresql_where=text("kind = 'member'"),
            sqlite_where=text("kind = 'member'"),
        ),
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
    # Registered by the person and awaiting approval; inactive until approved.
    pending: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
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
    def member_account(self) -> bool:
        """Whether this login opens an approved party member's account; needs `party_member`."""
        from backend.models.enums import PartyMemberStatus

        member = self.party_member
        return member is not None and member.status is PartyMemberStatus.APPROVED

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
