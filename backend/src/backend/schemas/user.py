"""User in and out of the API."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from backend.models.enums import UserRole
from backend.schemas.common import ORMModel, WriteModel


class UserRead(ORMModel):
    """Excludes password_hash, is_superuser and last_login_at."""

    id: uuid.UUID
    username: str
    email: str
    first_name: str
    last_name: str
    full_name: str
    phone: str
    role: UserRole
    is_active: bool
    created_at: datetime


class UserCreate(WriteModel):
    """A login for the campaign team. Managers and mobilizers only."""

    username: str = Field(min_length=3, max_length=150, pattern=r"^[A-Za-z0-9._-]+$")
    role: Literal[UserRole.MANAGER, UserRole.MOBILIZER]
    first_name: str = Field(default="", max_length=150)
    last_name: str = Field(default="", max_length=150)
    phone: str = Field(default="", max_length=20)
    email: str = Field(default="", max_length=254)

    # Required for a mobilizer: without it they sign in to an empty app.
    campaign: uuid.UUID | None = None
    ward: uuid.UUID | None = None
    registration_centre: uuid.UUID | None = None


class UserCreated(ORMModel):
    """The new account. `password` is shown this once and never again."""

    id: uuid.UUID
    username: str
    full_name: str
    role: UserRole
    phone: str
    password: str
    mobilizer: uuid.UUID | None = None
    ward_name: str | None = None
