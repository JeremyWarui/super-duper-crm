"""Sign-in, sign-up, and what they return."""

import uuid
from typing import Literal

from pydantic import Field

from backend.models.enums import UserRole
from backend.schemas.common import ORMModel, WriteModel


class LoginRequest(WriteModel):
    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=1)


class RegisterRequest(WriteModel):
    """A self-serve sign-up, which owns nothing until it sets a campaign up.

    A mobilizer is not registrable: they need a campaign and a ward, so they are
    added from inside a campaign by `POST /api/users/`.
    """

    username: str = Field(min_length=3, max_length=150, pattern=r"^[A-Za-z0-9._-]+$")
    password: str = Field(min_length=8, max_length=128)
    role: Literal[UserRole.CANDIDATE, UserRole.MANAGER]
    first_name: str = Field(default="", max_length=150)
    last_name: str = Field(default="", max_length=150)
    phone: str = Field(default="", max_length=20)
    email: str = Field(default="", max_length=254)


class LoginUser(ORMModel):
    """The caller's own identity, small enough to keep in the browser."""

    id: uuid.UUID
    username: str
    full_name: str
    role: UserRole


class LoginResponse(ORMModel):
    token: str
    user: LoginUser
