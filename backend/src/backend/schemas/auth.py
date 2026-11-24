"""Sign-in, and what it returns."""

import uuid

from pydantic import Field

from backend.models.enums import LinkPurpose, UserRole
from backend.schemas.common import ORMModel, Password, WriteModel


class LoginRequest(WriteModel):
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1)


class LoginUser(ORMModel):
    """The caller's identity, kept by the browser."""

    id: uuid.UUID
    username: str
    full_name: str
    role: UserRole | None
    is_superuser: bool


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
    password: Password
