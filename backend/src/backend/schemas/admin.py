"""What the admin console reads and sends."""

import uuid

from pydantic import Field

from backend.models.enums import UserRole
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


class AdminCampaignRead(ORMModel):
    id: uuid.UUID
    title: str
    office_level: str
    candidate: str
    election_date: str | None
    members: list[MemberRead]
    wards: list[AdminWardRead]
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
    """A new login, optionally put on a campaign, and a ward for a mobilizer."""

    role: UserRole
    campaign: uuid.UUID | None = None
    ward: uuid.UUID | None = None


class AdminUserCreated(NewLogin):
    role: UserRole


class CampaignRename(WriteModel):
    title: str = Field(min_length=1, max_length=150)
