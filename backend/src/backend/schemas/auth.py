"""Sign-in, and what it returns."""

import uuid

from pydantic import Field, field_validator

from backend.models.enums import PartyRoleName, UserKind, UserRole
from backend.schemas.common import ORMModel, WriteModel


class LoginRequest(WriteModel):
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1)


class LoginUser(ORMModel):
    """The caller's identity, kept by the browser."""

    id: uuid.UUID
    username: str
    full_name: str
    role: UserRole | None
    kind: UserKind
    is_superuser: bool
    party_roles: list[PartyRoleName]
    # Whether this login opens an approved party member's account.
    member_account: bool

    @field_validator("party_roles", mode="before")
    @classmethod
    def _names(cls, held: list) -> list:
        """Accepts the user's `PartyRole` rows or plain names."""
        return [getattr(item, "role", item) for item in held]


class LoginResponse(ORMModel):
    token: str
    user: LoginUser
