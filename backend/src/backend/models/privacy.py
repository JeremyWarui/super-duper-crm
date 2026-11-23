"""A data subject's request to the campaign, logged with the date it is due."""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    campaign_ref,
    choice_type,
    user_ref,
)
from backend.models.enums import DataRequestKind, DataRequestStatus


class DataRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "data_requests"

    campaign_id: Mapped[uuid.UUID] = campaign_ref()
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
