"""What a hosted campaign chooses to show the party: three switches, all off until the candidate
turns one on."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class CampaignSharing(Base):
    """One row per campaign once its candidate first changes a switch; no row means all off."""

    __tablename__ = "campaign_sharing"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="CASCADE"), primary_key=True
    )
    event_reach: Mapped[bool] = mapped_column(Boolean, default=False)
    ward_coverage: Mapped[bool] = mapped_column(Boolean, default=False)
    supporter_counts: Mapped[bool] = mapped_column(Boolean, default=False)
    changed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
