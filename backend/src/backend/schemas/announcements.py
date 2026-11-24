"""Announcements to a unit's team."""

import uuid
from datetime import datetime

from pydantic import Field

from backend.schemas.common import ORMModel, WriteModel


class AnnouncementSend(WriteModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=1000)
    # Both blank: the whole campaign. A centre reaches that centre's team.
    ward: uuid.UUID | None = None
    centre: uuid.UUID | None = None


class AnnouncementRead(ORMModel):
    id: uuid.UUID
    title: str
    body: str
    # "Whole campaign", "Mwiki ward" or "Mwiki Primary centre".
    unit: str
    author: str
    created_at: datetime
    # For whoever may announce: how many it went to and how many have read it.
    recipients: int | None = None
    read: int | None = None
    # For a recipient: whether they have opened it.
    read_by_me: bool | None = None


class AnnouncementSent(ORMModel):
    announcement: AnnouncementRead
    # How many devices showed the alert.
    alerted: int
