"""A data subject's request to the party or a workspace, logged with the date it is due."""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_type, user_ref
from backend.models.enums import DataRequestKind, DataRequestStatus


class DataRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """`campaign_id` NULL is a request to the party."""

    __tablename__ = "data_requests"

    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="CASCADE"), default=None, index=True
    )
    kind: Mapped[DataRequestKind] = mapped_column(choice_type(DataRequestKind, "data_request_kind"))
    requester_name: Mapped[str] = mapped_column(String(150))
    requester_contact: Mapped[str] = mapped_column(String(254))
    details: Mapped[str] = mapped_column(Text, default="")
    received_on: Mapped[date] = mapped_column(Date)
    due_on: Mapped[date] = mapped_column(Date)
    status: Mapped[DataRequestStatus] = mapped_column(
        choice_type(DataRequestStatus, "data_request_status"), default=DataRequestStatus.OPEN
    )
    answer: Mapped[str] = mapped_column(Text, default="")
    logged_by_id: Mapped[uuid.UUID | None] = user_ref()
    answered_by_id: Mapped[uuid.UUID | None] = user_ref()
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
