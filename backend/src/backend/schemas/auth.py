"""Sign-up, sign-in, and what they return."""

import uuid
from typing import Literal

from pydantic import Field

from backend.models.enums import UserRole
from backend.schemas.common import LoginDetails, ORMModel, WriteModel


class LoginRequest(WriteModel):
    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=1)


class RegisterRequest(LoginDetails):
    """A self-serve sign-up; only a candidate or a manager may register."""

    password: str = Field(min_length=8, max_length=128)
    role: Literal[UserRole.CANDIDATE, UserRole.MANAGER]


class LoginUser(ORMModel):
    """The caller's identity, kept by the browser."""

    id: uuid.UUID
    username: str
    full_name: str
    role: UserRole
    is_superuser: bool


class LoginResponse(ORMModel):
    token: str
    user: LoginUser
