"""What the admin console reads and sends."""

import uuid

from pydantic import Field, field_validator

from backend.models.enums import UserRole
from backend.schemas.common import (
    CampaignTitle,
    Invite,
    LoginDetails,
    Named,
    NewLogin,
    ORMModel,
    WriteModel,
)
from backend.schemas.site import Email


class Totals(ORMModel):
    campaigns: int
    users: int
    members: int
    targets: int
    mobilizers: int
    events: int
    supporters: int


class MemberRead(ORMModel):
    user_id: uuid.UUID
    username: str
    full_name: str
    role: UserRole


AdminWardRead = Named


class AdminCentreRead(ORMModel):
    id: uuid.UUID
    name: str
    ward: uuid.UUID


class AdminCampaignRead(ORMModel):
    id: uuid.UUID
    title: str
    office_level: str
    candidate: str
    election_date: str | None
    members: list[MemberRead]
    # Empty for a national seat, whose forms pick the ward from the public places.
    national: bool = False
    wards: list[AdminWardRead]
    # The centres with a target; empty unless the race is run by centre (MCA).
    centres: list[AdminCentreRead] = []
    targets: int
    mobilizers: int
    events: int
    supporters: int
    votes_needed: int
    votes_committed: int


class AdminUserRead(ORMModel):
    """A login and the title of the campaign it is on, if any."""

    id: uuid.UUID
    username: str
    full_name: str
    email: str
    phone: str
    role: UserRole | None
    is_active: bool
    is_superuser: bool
    last_login_at: str | None
    campaign: str | None


class Overview(ORMModel):
    totals: Totals
    campaigns: list[AdminCampaignRead]


class PasswordResult(ORMModel):
    """How the reset link went out."""

    username: str
    sent: Invite


class ActiveSet(WriteModel):
    active: bool


class EmailSet(WriteModel):
    email: Email = Field(min_length=3)

    @field_validator("email", mode="before")
    @classmethod
    def _trim(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class MemberAdd(WriteModel):
    """The place a member takes is their login's role."""

    user: uuid.UUID


class AdminUserCreate(LoginDetails):
    """A new login, optionally put on a campaign; a mobilizer gets a ward, or an MCA centre."""

    role: UserRole
    campaign: uuid.UUID | None = None
    ward: uuid.UUID | None = None
    registration_centre: uuid.UUID | None = None


class AdminUserCreated(NewLogin):
    role: UserRole


class CampaignRename(WriteModel):
    title: CampaignTitle
