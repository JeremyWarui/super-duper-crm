"""Campaign, Target, Mobilizer, Event and Supporter, in and out of the API.

A foreign key travels under the related model's bare name: `ward`, not `ward_id`.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import AliasPath, Field, ValidationInfo, field_validator

from backend.models.enums import EventStatus, OfficeLevel, OperationalGrain, SupportLevel
from backend.schemas.common import ORMModel, WriteModel

# ------------------------------------------------------------------ campaign


class CampaignRead(ORMModel):
    id: uuid.UUID
    candidate: uuid.UUID = Field(validation_alias="candidate_id")
    title: str
    office_level: OfficeLevel
    county: uuid.UUID | None = Field(default=None, validation_alias="county_id")
    constituency: uuid.UUID | None = Field(default=None, validation_alias="constituency_id")
    ward: uuid.UUID | None = Field(default=None, validation_alias="ward_id")
    election_date: date | None
    operational_grain: OperationalGrain
    created_at: datetime


class NewCandidate(WriteModel):
    """An aspirant being created by whoever is setting the campaign up."""

    username: str = Field(min_length=3, max_length=150, pattern=r"^[A-Za-z0-9._-]+$")
    first_name: str = Field(default="", max_length=150)
    last_name: str = Field(default="", max_length=150)
    phone: str = Field(default="", max_length=20)


class CampaignSetup(WriteModel):
    """The seat, where it is, and whose it is.

    A campaign belongs to its candidate, never to whoever filled the form in.
    A manager must name one; a candidate gets themselves.
    """

    title: str = Field(min_length=1, max_length=150)
    office_level: OfficeLevel
    election_date: date | None = None
    county: uuid.UUID | None = None
    constituency: uuid.UUID | None = None
    ward: uuid.UUID | None = None
    candidate: uuid.UUID | None = None
    new_candidate: NewCandidate | None = None


class SetupSummary(ORMModel):
    """What generating the targets produced."""

    grain: OperationalGrain
    units: int
    total_registered: int
    win_number: int
    note: str | None = None


class CandidateLogin(ORMModel):
    """A candidate created during setup. `password` is shown once."""

    id: uuid.UUID
    username: str
    full_name: str
    password: str


class CampaignSetupResponse(CampaignRead):
    setup: SetupSummary
    candidate_login: CandidateLogin | None = None


# -------------------------------------------------------------------- target


class TargetRead(ORMModel):
    id: uuid.UUID
    campaign: uuid.UUID = Field(validation_alias="campaign_id")
    ward: uuid.UUID = Field(validation_alias="ward_id")
    ward_name: str = Field(validation_alias=AliasPath("ward", "name"))
    registration_centre: uuid.UUID | None = Field(
        default=None, validation_alias="registration_centre_id"
    )
    centre_name: str | None = Field(
        default=None, validation_alias=AliasPath("registration_centre", "name")
    )
    registered_voters: int | None
    projected_turnout_pct: Decimal | None
    votes_needed: int | None
    votes_committed: int
    votes_remaining: int | None
    progress_pct: float


class TargetCreate(WriteModel):
    campaign: uuid.UUID
    ward: uuid.UUID
    registration_centre: uuid.UUID | None = None
    projected_turnout_pct: Decimal | None = Field(default=None, ge=0, le=100)
    votes_committed: int = Field(default=0, ge=0)


class TargetUpdate(WriteModel):
    """The win number is recomputed from whatever changed."""

    projected_turnout_pct: Decimal | None = Field(default=None, ge=0, le=100)
    votes_committed: int | None = Field(default=None, ge=0)


# ----------------------------------------------------------------- mobilizer


class MobilizerRead(ORMModel):
    id: uuid.UUID
    campaign: uuid.UUID = Field(validation_alias="campaign_id")
    ward: uuid.UUID = Field(validation_alias="ward_id")
    ward_name: str = Field(validation_alias=AliasPath("ward", "name"))
    registration_centre: uuid.UUID | None = Field(
        default=None, validation_alias="registration_centre_id"
    )
    user: uuid.UUID | None = Field(default=None, validation_alias="user_id")
    full_name: str
    phone: str
    created_at: datetime


class MobilizerCreate(WriteModel):
    campaign: uuid.UUID
    ward: uuid.UUID
    registration_centre: uuid.UUID | None = None
    user: uuid.UUID | None = None
    full_name: str = Field(min_length=1, max_length=150)
    phone: str = Field(default="", max_length=20)


# --------------------------------------------------------------------- event


class EventRead(ORMModel):
    id: uuid.UUID
    campaign: uuid.UUID = Field(validation_alias="campaign_id")
    ward: uuid.UUID = Field(validation_alias="ward_id")
    ward_name: str = Field(validation_alias=AliasPath("ward", "name"))
    registration_centre: uuid.UUID | None = Field(
        default=None, validation_alias="registration_centre_id"
    )
    mobilizer: uuid.UUID | None = Field(default=None, validation_alias="mobilizer_id")
    title: str
    venue: str
    scheduled_date: datetime | None
    status: EventStatus
    number_reached: int
    number_attended: int
    turnout_pct: float


class EventCreate(WriteModel):
    campaign: uuid.UUID
    ward: uuid.UUID
    registration_centre: uuid.UUID | None = None
    mobilizer: uuid.UUID | None = None
    title: str = Field(default="", max_length=150)
    venue: str = Field(default="", max_length=150)
    scheduled_date: datetime | None = None
    status: EventStatus = EventStatus.PLANNED


class EventRecord(WriteModel):
    """Who was invited, and who came."""

    number_reached: int = Field(ge=0)
    number_attended: int = Field(ge=0)

    @field_validator("number_attended")
    @classmethod
    def _no_more_than_reached(cls, value: int, info: ValidationInfo) -> int:
        reached: Any = info.data.get("number_reached")
        if reached is not None and value > reached:
            raise ValueError("Attendance cannot exceed the number reached.")
        return value


# ----------------------------------------------------------------- supporter


class SupporterRead(ORMModel):
    id: uuid.UUID
    campaign: uuid.UUID = Field(validation_alias="campaign_id")
    ward: uuid.UUID | None = Field(default=None, validation_alias="ward_id")
    mobilizer: uuid.UUID | None = Field(default=None, validation_alias="mobilizer_id")
    full_name: str
    phone: str
    support_level: SupportLevel
    consent_given: bool
    created_at: datetime


class SupporterCreate(WriteModel):
    campaign: uuid.UUID
    ward: uuid.UUID | None = None
    mobilizer: uuid.UUID | None = None
    full_name: str = Field(min_length=1, max_length=150)
    phone: str = Field(default="", max_length=20)
    support_level: SupportLevel = SupportLevel.UNDECIDED
    consent_given: bool

    @field_validator("consent_given")
    @classmethod
    def _consent_is_required(cls, value: bool) -> bool:
        # Data Protection Act 2019.
        if not value:
            raise ValueError("Consent is required before we can store these details.")
        return value


class EventInvite(WriteModel):
    """Who to invite, and what to say."""

    message: str = Field(min_length=1, max_length=918)  # six SMS parts
    # Blank invites everyone in the event's ward.
    support_levels: list[SupportLevel] = Field(default_factory=list)
    whole_campaign: bool = False
    dry_run: bool = False


class InviteRecipient(ORMModel):
    phone: str
    status: str
    detail: str = ""


class EventInviteResult(ORMModel):
    """`delivered` is False whenever nothing left."""

    provider: str
    delivered: bool
    dry_run: bool
    message: str
    parts: int
    supporters_matched: int
    requested: int
    accepted: list[InviteRecipient]
    rejected: list[InviteRecipient]
    detail: str
    number_reached: int
