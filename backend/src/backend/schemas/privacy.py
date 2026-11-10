"""Data subject requests, people who can be erased, and a campaign's close and retention."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from backend.schemas.common import Plain, PlainLines, WriteModel

Kind = Literal["access", "correction", "erasure"]
Status = Literal["open", "done"]
Line = Plain
Lines = PlainLines


class DataRequestCreate(WriteModel):
    kind: Kind
    requester_name: Line = Field(min_length=1, max_length=150)
    requester_contact: Line = Field(min_length=1, max_length=254)
    details: Lines = Field(default="", max_length=4000)
    received_on: date | None = None
    due_on: date | None = None


class DataRequestUpdate(WriteModel):
    due_on: date | None = None
    answer: Lines | None = Field(default=None, max_length=4000)
    status: Status | None = None


class DataRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: Kind
    requester_name: str
    requester_contact: str
    details: str
    received_on: date
    due_on: date
    status: Status
    answer: str
    answered_at: datetime | None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def overdue(self) -> bool:
        return self.status == "open" and self.due_on < date.today()


class LeftTeamRead(BaseModel):
    """A mobilizer's or agent's sign-up whose person is off the team; erasable."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    role: str
    status: str
    created_at: datetime


class CampaignClose(BaseModel):
    closed_at: datetime | None
    retention_months: int
    erase_from: datetime | None
    supporters_erased_at: datetime | None
    supporters: int
    erased: int


class Retention(WriteModel):
    retention_months: int = Field(ge=1, le=60)


class Erased(BaseModel):
    erased: int


class WithdrawalLink(BaseModel):
    url: str
    can_text: bool
