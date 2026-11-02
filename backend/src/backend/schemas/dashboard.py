"""The party dashboard: counts across the registers, campaigns and subscriptions."""

import uuid
from datetime import date

from pydantic import BaseModel

from backend.models import Seat, VolunteerInterest


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
    interest: VolunteerInterest
    count: int


class DashboardRevenue(BaseModel):
    start: date
    end: date
    total_kes: int
    count: int


class Dashboard(BaseModel):
    approved_members: int
    pending_applications: int
    active_volunteers: int
    volunteers_by_county: list[CountyCount]
    volunteers_by_interest: list[InterestCount]
    approved_aspirants: int
    active_campaigns: int
    active_subscriptions: int
    events_from: date
    events_to: date
    upcoming_events_by_county: list[CountyCount]
    upcoming_events_by_seat: list[SeatCount]
    campaigns_by_county_and_seat: list[CountySeatCount]
    revenue: DashboardRevenue
