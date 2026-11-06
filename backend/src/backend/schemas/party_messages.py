"""Party texts to members and volunteers: drafts, who they reach, and how they went."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from backend.schemas.common import WriteModel, plain_text
from backend.schemas.messages import BODY_MAX, DeliveryCounts

Audience = Literal["members", "volunteers"]


class Audiences(WriteModel):
    audience: Audience
    county: uuid.UUID | None = None
    ward: uuid.UUID | None = None


class PartyMessageDraft(Audiences):
    body: str = Field(min_length=1, max_length=BODY_MAX)

    @field_validator("body")
    @classmethod
    def _plain(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Write the message.")
        return plain_text(value, lines=True)


class PartyReach(BaseModel):
    recipients: int
    opted_out: int


class PartyMessageRead(BaseModel):
    id: uuid.UUID
    body: str
    audience: Audience
    place: str
    status: str
    drafted_by: str
    decided_by: str
    created_at: datetime
    decided_at: datetime | None
    note: str
    targeted: int
    recipients: int
    delivery: DeliveryCounts
    mine: bool


class PartyMessages(BaseModel):
    can_send: bool
    messages: list[PartyMessageRead]
