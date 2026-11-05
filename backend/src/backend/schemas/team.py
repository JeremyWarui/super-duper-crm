"""A campaign's own team, as its aspirant and manager see it."""

import uuid
from typing import Literal

from pydantic import Field

from backend.models.enums import UserRole
from backend.schemas.common import LoginDetails, NewLogin, ORMModel, WriteModel


class TeamMemberRead(ORMModel):
    id: uuid.UUID
    username: str
    full_name: str
    role: UserRole
    phone: str
    is_active: bool


class ManagerCreate(LoginDetails):
    """`replace` must be set when the campaign already has a manager."""

    replace: bool = False


class ManagerCreated(NewLogin):
    """`password` is shown this once; `replaced` names the manager taken off."""

    replaced: str | None = None


class StaffCreate(LoginDetails):
    role: Literal[UserRole.COORDINATOR, UserRole.COMMS]


class StaffCreated(NewLogin):
    """`password` is shown this once."""

    role: UserRole


class AreaWrite(WriteModel):
    """A coordinator's whole area; it replaces the one they have."""

    wards: list[uuid.UUID] = Field(default_factory=list, max_length=500)
    registration_centres: list[uuid.UUID] = Field(default_factory=list, max_length=2000)


class AreaRead(ORMModel):
    wards: list[uuid.UUID]
    registration_centres: list[uuid.UUID]
