"""Sign-in, and what it returns."""

import uuid

from pydantic import Field, field_validator

from backend.models.enums import LinkPurpose, PartyRoleName, UserKind, UserRole
from backend.schemas.common import ORMModel, WriteModel


class LoginRequest(WriteModel):
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1)
    # The authenticator or recovery code, for a login with 2-step on.
    code: str = Field(default="", max_length=20)


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
    # 2-step is on for this login; it needs 2-step and this session has not passed it.
    two_step_on: bool = False
    two_step_needed: bool = False

    @field_validator("party_roles", mode="before")
    @classmethod
    def _names(cls, held: list) -> list:
        """Accepts the user's `PartyRole` rows or plain names."""
        return [getattr(item, "role", item) for item in held]


class LoginResponse(ORMModel):
    token: str
    user: LoginUser


class ResetSent(ORMModel):
    detail: str


class ResetRequest(WriteModel):
    email: str = Field(min_length=1, max_length=254)


class LinkRead(ORMModel):
    """What a live sign-in link is for, and whose login it sets."""

    purpose: LinkPurpose
    username: str
    email: str


class LinkClaim(WriteModel):
    password: str = Field(min_length=8, max_length=128)
    code: str = Field(default="", max_length=20)


class AuthOptions(ORMModel):
    """Which ways of signing in this installation offers besides email and password."""

    google: bool


class GoogleFinish(WriteModel):
    handoff: str = Field(min_length=1, max_length=100)
    bind: str = Field(min_length=16, max_length=100)


class TwoStepStatus(ORMModel):
    on: bool
    required: bool
    recovery_left: int


class TwoStepStart(ORMModel):
    """The secret to type into an authenticator app, and the link its QR code holds."""

    secret: str
    uri: str


class TwoStepCode(WriteModel):
    code: str = Field(min_length=1, max_length=20)


class RecoveryCodes(ORMModel):
    """Shown once; each signs in once in place of an app code. Turning 2-step on also returns
    the session's new token."""

    codes: list[str]
    token: str | None = None
