"""Volunteer register schemas for membership officers."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from backend.models import ContactMethod, PartyMemberStatus, VolunteerStatus
from backend.schemas.common import ORMModel, WriteModel, plain_text
from backend.schemas.party import MemberPlace


class VolunteerRead(ORMModel):
    """A volunteer row as the officer's list shows it."""

    id: uuid.UUID
    member_id: uuid.UUID
    full_name: str
    phone: str
    ward: MemberPlace
    constituency: MemberPlace
    county: MemberPlace
    status: VolunteerStatus
    interests: list[str]
    preferred_contact: ContactMethod
    availability_notes: str | None
    member_status: PartyMemberStatus
    created_at: datetime


class VolunteerPage(BaseModel):
    total: int
    items: list[VolunteerRead]


class VolunteerUpdate(WriteModel):
    """An officer's change: a move between active and inactive, and the availability notes."""

    status: Literal["active", "inactive"] | None = None
    availability_notes: str | None = Field(default=None, max_length=2000)

    @field_validator("availability_notes")
    @classmethod
    def _plain(cls, value: str | None) -> str | None:
        return plain_text(value, lines=True)
