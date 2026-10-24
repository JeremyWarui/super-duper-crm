"""What the admin console reads and sends."""

import uuid
from datetime import date

from pydantic import Field

from backend.models.enums import Seat, UserRole
from backend.schemas.campaign import SetupSummary
from backend.schemas.common import LoginDetails, NewLogin, ORMModel, WriteModel


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


class AdminWardRead(ORMModel):
    id: uuid.UUID
    name: str


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
    role: UserRole
    is_active: bool
    is_superuser: bool
    last_login_at: str | None
    campaign: str | None


class Overview(ORMModel):
    totals: Totals
    campaigns: list[AdminCampaignRead]


class PasswordReset(WriteModel):
    """Blank generates one."""

    password: str | None = Field(default=None, min_length=8, max_length=128)


class PasswordResult(ORMModel):
    """`password` is shown this once."""

    username: str
    password: str


class ActiveSet(WriteModel):
    active: bool


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


class AdminCampaignCreate(WriteModel):
    """A campaign on its seat and area, with new logins for its aspirant and optional manager."""

    title: str = Field(min_length=1, max_length=150)
    seat: Seat
    election_date: date | None = None
    county: uuid.UUID | None = None
    constituency: uuid.UUID | None = None
    ward: uuid.UUID | None = None
    aspirant: LoginDetails
    manager: LoginDetails | None = None


class AdminCampaignCreated(ORMModel):
    """`logins` carry passwords shown this once."""

    campaign: AdminCampaignRead
    setup: SetupSummary
    logins: list[AdminUserCreated]


class CampaignRename(WriteModel):
    title: str = Field(min_length=1, max_length=150)
