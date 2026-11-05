"""Who works on a campaign, and in what capacity."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_type
from backend.models.enums import UserRole

if TYPE_CHECKING:
    from backend.models.campaign import Campaign
    from backend.models.geography import RegistrationCentre, Ward
    from backend.models.user import User


class CampaignMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A login's place on its one campaign; the member whose role is candidate owns it."""

    __tablename__ = "campaign_members"
    __table_args__ = (
        # The role here always equals the user's own role.
        ForeignKeyConstraint(["user_id", "role"], ["users.id", "users.role"], ondelete="CASCADE"),
        Index("uq_campaign_members_one_campaign_per_user", "user_id", unique=True),
        Index(
            "uq_campaign_members_one_candidate",
            "campaign_id",
            unique=True,
            postgresql_where=text("role = 'candidate'"),
            sqlite_where=text("role = 'candidate'"),
        ),
        Index(
            "uq_campaign_members_one_manager",
            "campaign_id",
            unique=True,
            postgresql_where=text("role = 'manager'"),
            sqlite_where=text("role = 'manager'"),
        ),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    role: Mapped[UserRole] = mapped_column(choice_type(UserRole, "member_role"))

    campaign: Mapped["Campaign"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="memberships")
    areas: Mapped[list["CampaignMemberArea"]] = relationship(
        back_populates="member", cascade="all, delete-orphan", passive_deletes=True
    )

    def __str__(self) -> str:
        return f"{self.user_id} on {self.campaign_id} as {self.role.label}"


class CampaignMemberArea(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A ward or a registration centre in a coordinator's area; exactly one of the two.

    Only a coordinator may hold rows; the database does not enforce that.
    """

    __tablename__ = "campaign_member_areas"
    __table_args__ = (
        CheckConstraint("(ward_id IS NULL) <> (registration_centre_id IS NULL)", name="one_place"),
        UniqueConstraint("campaign_member_id", "ward_id"),
        UniqueConstraint("campaign_member_id", "registration_centre_id"),
    )

    campaign_member_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("campaign_members.id", ondelete="CASCADE"), index=True
    )
    ward_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("wards.id", ondelete="RESTRICT"), default=None
    )
    registration_centre_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("registration_centres.id", ondelete="RESTRICT"), default=None
    )

    member: Mapped[CampaignMember] = relationship(back_populates="areas")
    ward: Mapped["Ward | None"] = relationship()
    registration_centre: Mapped["RegistrationCentre | None"] = relationship()
