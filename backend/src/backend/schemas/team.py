"""A campaign's own team, as its aspirant and manager see it."""

import uuid

from backend.models.enums import UserRole
from backend.schemas.common import LoginDetails, NewLogin, ORMModel


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


class TeamPassword(ORMModel):
    """`password` is shown this once."""

    username: str
    password: str
