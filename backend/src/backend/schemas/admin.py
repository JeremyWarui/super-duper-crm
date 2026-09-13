"""What the admin console reads and sends."""

import uuid

from pydantic import Field

from backend.models.enums import UserRole
from backend.schemas.common import ORMModel, WriteModel


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


class WardRead(ORMModel):
    id: uuid.UUID
    name: str


class AdminCampaignRead(ORMModel):
    id: uuid.UUID
    title: str
    office_level: str
    candidate: str
    election_date: str | None
    members: list[MemberRead]
    wards: list[WardRead]
    targets: int
    mobilizers: int
    events: int
    supporters: int
    votes_needed: int
    votes_committed: int


class AdminUserRead(ORMModel):
    """A login. Never carries a hash, and never carries a password."""

    id: uuid.UUID
    username: str
    full_name: str
    email: str
    phone: str
    role: UserRole
    is_active: bool
    is_superuser: bool
    last_login_at: str | None
    campaigns: list[tuple[uuid.UUID, str, UserRole]]


class Overview(ORMModel):
    totals: Totals
    campaigns: list[AdminCampaignRead]


class PasswordReset(WriteModel):
    """Blank generates one."""

    password: str | None = Field(default=None, min_length=8, max_length=128)


class PasswordResult(ORMModel):
    """`password` is shown this once and never again."""

    username: str
    password: str


class ActiveSet(WriteModel):
    active: bool


class MemberAdd(WriteModel):
    """The place a member takes is their login's role, so it is not asked for."""

    user: uuid.UUID


class AdminUserCreate(WriteModel):
    """A new login, optionally placed on a campaign as it is made."""

    username: str = Field(min_length=3, max_length=150, pattern=r"^[A-Za-z0-9._-]+$")
    role: UserRole
    first_name: str = Field(default="", max_length=150)
    last_name: str = Field(default="", max_length=150)
    email: str = Field(default="", max_length=254)
    phone: str = Field(default="", max_length=20)
    campaign: uuid.UUID | None = None
    ward: uuid.UUID | None = None


class AdminUserCreated(ORMModel):
    """`password` is shown this once and never again."""

    id: uuid.UUID
    username: str
    full_name: str
    role: UserRole
    password: str


class CampaignRename(WriteModel):
    title: str = Field(min_length=1, max_length=150)
