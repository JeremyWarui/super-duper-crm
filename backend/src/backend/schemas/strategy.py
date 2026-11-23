"""The strategy read."""

import uuid
from typing import Literal

from pydantic import BaseModel


class UnitRead(BaseModel):
    unit: str
    ward: uuid.UUID
    constituency_name: str = ""
    registration_centre: uuid.UUID | None = None
    needed: int
    committed: int
    gap: int
    progress: float
    events: int
    has_mobilizer: bool
    share: float = 0.0


class GroupRead(BaseModel):
    """The units of one county or constituency, rolled up."""

    id: uuid.UUID
    name: str
    units: int
    needed: int
    committed: int
    gap: int
    progress: float
    unstaffed: int
    quiet: int


class NoteRead(BaseModel):
    tone: str
    title: str
    text: str


class StrategyRead(BaseModel):
    win_number: int
    committed: int
    progress_pct: float
    total_registered: int
    total_cast: int
    # Counts over every unit, whatever `units` is narrowed to.
    unit_count: int = 0
    short_count: int = 0
    staffed_count: int = 0
    quiet_count: int = 0
    # The units in the county or constituency asked for; none for a national seat asked for
    # none, which reads `groups` instead.
    units: list[UnitRead]
    # The asked-for units rolled up by county for a national seat, by constituency within a
    # county; empty below that.
    group_level: Literal["county", "constituency"] | None = None
    groups: list[GroupRead] = []
    notes: list[NoteRead]
