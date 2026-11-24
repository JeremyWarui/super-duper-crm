"""Turnout scenarios: the preview of a seat's targets, setting one for the team, and notices."""

import uuid
from datetime import datetime

from backend.models import TargetReliability, TurnoutScenario
from backend.schemas.common import ORMModel, WriteModel


class ScenarioFigures(ORMModel):
    scenario: TurnoutScenario
    turnout_pct: str
    projected: int
    majority: int
    target: int


class PreviewUnit(ORMModel):
    ward: uuid.UUID
    registration_centre: uuid.UUID | None
    name: str
    weight_pct: str
    target: int
    # What the unit is asked for now, under the set scenario.
    set_target: int | None
    supporters: int


class TargetsPreview(ORMModel):
    scenario: TurnoutScenario
    set_scenario: TurnoutScenario
    set_by: uuid.UUID | None
    set_at: datetime | None
    seat: str
    registered_voters: int
    winner_votes: int | None
    valid_votes: int | None
    share_pct: str
    typical_pct: str | None
    reliability: TargetReliability
    two_candidate: bool
    uses_2017: bool
    scenarios: list[ScenarioFigures]
    seat_target: int
    set_seat_target: int
    majority: int
    supporters: int
    # Units whose target differs from the set one, across the whole seat.
    units_changed: int
    units: list[PreviewUnit]


class ScenarioSet(WriteModel):
    scenario: TurnoutScenario


class ScenarioSetResult(ORMModel):
    scenario: TurnoutScenario
    seat_target_from: int
    seat_target_to: int
    units_changed: int
    notified: int


class NoticeRead(ORMModel):
    id: uuid.UUID
    text: str
    url: str
    created_at: datetime
    read_at: datetime | None = None
    detail: str = ""
    # Who caused it; blank when nobody did.
    sender: str = ""
