"""Read schemas for Campaign, Target, Mobilizer, Event and Supporter.

Derived values that need no relationship loaded are included (`operational_grain`,
`votes_remaining`, `progress_pct`, `turnout_pct`). `Campaign.area` and
`Target.registered_voters` are not: both read a related row, so serializing them
by default would turn every response into a silent extra query - or, under an
AsyncSession, an error.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from backend.models.enums import EventStatus, OfficeLevel, OperationalGrain, SupportLevel
from backend.schemas.common import ORMModel


class CampaignRead(ORMModel):
    id: uuid.UUID
    candidate_id: uuid.UUID
    title: str
    office_level: OfficeLevel
    county_id: uuid.UUID | None
    constituency_id: uuid.UUID | None
    ward_id: uuid.UUID | None
    election_date: date | None
    operational_grain: OperationalGrain
    created_at: datetime


class TargetRead(ORMModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    ward_id: uuid.UUID
    registration_centre_id: uuid.UUID | None
    projected_turnout_pct: Decimal | None
    votes_needed: int | None
    votes_committed: int
    votes_remaining: int | None
    progress_pct: float


class MobilizerRead(ORMModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    ward_id: uuid.UUID
    registration_centre_id: uuid.UUID | None
    user_id: uuid.UUID | None
    full_name: str
    phone: str
    created_at: datetime


class EventRead(ORMModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    ward_id: uuid.UUID
    registration_centre_id: uuid.UUID | None
    mobilizer_id: uuid.UUID | None
    title: str
    venue: str
    scheduled_date: datetime | None
    status: EventStatus
    number_reached: int
    number_attended: int
    turnout_pct: float


class SupporterRead(ORMModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    ward_id: uuid.UUID | None
    mobilizer_id: uuid.UUID | None
    full_name: str
    phone: str
    support_level: SupportLevel
    consent_given: bool
    created_at: datetime
