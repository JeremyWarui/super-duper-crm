"""The party dashboard: counts across the registers and campaigns."""

import uuid
from datetime import date

from pydantic import BaseModel

from backend.models import Seat, VolunteerArea


class CountyCount(BaseModel):
    county_id: uuid.UUID
    county: str
    count: int


class SeatCount(BaseModel):
    seat: Seat
    count: int


class CountySeatCount(BaseModel):
    county_id: uuid.UUID
    county: str
    seat: Seat
    count: int


class InterestCount(BaseModel):
    interest: VolunteerArea
    count: int


class Dashboard(BaseModel):
    approved_members: int
    pending_applications: int
    active_volunteers: int
    volunteers_by_county: list[CountyCount]
    volunteers_by_interest: list[InterestCount]
    approved_aspirants: int
    active_campaigns: int
    events_from: date
    events_to: date
    upcoming_events_by_county: list[CountyCount]
    upcoming_events_by_seat: list[SeatCount]
    campaigns_by_county_and_seat: list[CountySeatCount]
    # Hosted workspaces only above; the party's own workspace is counted here.
    party_workspace: "PartyWorkspaceTotals | None" = None
    applications_by_county: list[CountyCount] = []
    applications_by_coordinator: list["CoordinatorCount"] = []


class PartyWorkspaceTotals(BaseModel):
    supporters: int
    mobilizers: int
    upcoming_events: int


class CoordinatorCount(BaseModel):
    """Applications that came through one coordinator's recruitment links."""

    coordinator: str
    count: int


Dashboard.model_rebuild()
