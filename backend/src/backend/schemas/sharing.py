"""A hosted campaign's party feed and sharing switches, and what the party reads of them."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel

from backend.models import Seat
from backend.schemas.common import WriteModel


class Switches(BaseModel):
    event_reach: bool
    ward_coverage: bool
    supporter_counts: bool


class SwitchesWrite(Switches):
    model_config = WriteModel.model_config


class FeedPost(BaseModel):
    id: uuid.UUID
    title: str
    body: str
    event_date: date | None
    venue: str
    published_on: date | None


class WardCount(BaseModel):
    ward_id: uuid.UUID
    ward: str
    count: int


class Change(BaseModel):
    at: datetime
    by: str
    switch: str
    on: bool


class PartyFeed(BaseModel):
    events: list[FeedPost]
    notices: list[FeedPost]
    members_by_ward: list[WardCount]
    sharing: Switches
    can_change: bool
    history: list[Change]


class EventReach(BaseModel):
    events: int
    reached: int
    attended: int


class Coverage(BaseModel):
    wards: int
    covered: list[WardCount]


class SharedCampaign(BaseModel):
    """One hosted campaign's shared counts; a share it has not turned on is null."""

    id: uuid.UUID
    title: str
    seat: Seat | None
    event_reach: EventReach | None
    ward_coverage: Coverage | None
    supporter_counts: list[WardCount] | None
