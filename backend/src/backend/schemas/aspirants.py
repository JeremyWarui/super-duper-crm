"""Nominations as the nominations officer reads and writes them."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from backend.models import AspirantStatus, Seat
from backend.schemas.common import ORMModel, WriteModel, plain_text
from backend.schemas.party import MemberPlace


class CandidateRead(ORMModel):
    """An approved member who can be nominated; never their phone."""

    id: uuid.UUID
    full_name: str
    ward: MemberPlace


class AspirantArea(BaseModel):
    level: str
    id: uuid.UUID
    name: str


class AspirantRead(ORMModel):
    id: uuid.UUID
    member: CandidateRead
    seat: Seat
    area: AspirantArea
    status: AspirantStatus
    status_reason: str | None
    decided_at: datetime | None
    campaign_id: uuid.UUID | None
    created_at: datetime


class AspirantPage(BaseModel):
    total: int
    items: list[AspirantRead]


class AspirantCreate(WriteModel):
    member: uuid.UUID
    seat: Seat
    county: uuid.UUID | None = None
    constituency: uuid.UUID | None = None
    ward: uuid.UUID | None = None


class AspirantMove(WriteModel):
    status: AspirantStatus
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("reason")
    @classmethod
    def _plain(cls, value: str | None) -> str | None:
        return plain_text(value, lines=True)
