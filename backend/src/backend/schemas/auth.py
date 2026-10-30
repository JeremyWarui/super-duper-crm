"""Sign-in, and what it returns."""

import uuid

from pydantic import Field, field_validator

from backend.models.enums import PartyRoleName, UserRole
from backend.schemas.common import ORMModel, WriteModel


class LoginRequest(WriteModel):
    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=1)


class LoginUser(ORMModel):
    """The caller's identity, kept by the browser."""

    id: uuid.UUID
    username: str
    full_name: str
    role: UserRole | None
    is_superuser: bool
    party_roles: list[PartyRoleName]

    @field_validator("party_roles", mode="before")
    @classmethod
    def _names(cls, held: list) -> list:
        """Accepts the user's `PartyRole` rows or plain names."""
        return [getattr(item, "role", item) for item in held]


class LoginResponse(ORMModel):
    token: str
    user: LoginUser
