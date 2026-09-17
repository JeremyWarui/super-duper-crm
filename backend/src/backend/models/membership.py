"""Who works on a campaign, and in what capacity."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_type
from backend.models.enums import UserRole

if TYPE_CHECKING:
    from backend.models.campaign import Campaign
    from backend.models.user import User


class CampaignMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A login's place on its one campaign; the member whose role is candidate owns it."""

    __tablename__ = "campaign_members"
    __table_args__ = (
        Index("uq_campaign_members_one_campaign_per_user", "user_id", unique=True),
        Index(
            "uq_campaign_members_one_candidate",
            "campaign_id",
            unique=True,
            postgresql_where=text("role = 'candidate'"),
            sqlite_where=text("role = 'candidate'"),
        ),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[UserRole] = mapped_column(choice_type(UserRole, "member_role"))

    campaign: Mapped["Campaign"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="memberships")

    def __str__(self) -> str:
        return f"{self.user_id} on {self.campaign_id} as {self.role.label}"
