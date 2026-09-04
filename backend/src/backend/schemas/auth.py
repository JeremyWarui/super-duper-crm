"""Sign-in request and response."""

import uuid

from pydantic import Field

from backend.models.enums import UserRole
from backend.schemas.common import ORMModel, WriteModel


class LoginRequest(WriteModel):
    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=1)


class LoginUser(ORMModel):
    """The caller's own identity, small enough to keep in the browser."""

    id: uuid.UUID
    username: str
    full_name: str
    role: UserRole


class LoginResponse(ORMModel):
    token: str
    user: LoginUser
