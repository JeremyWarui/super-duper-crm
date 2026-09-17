"""User in and out of the API."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator
from pydantic_core import PydanticCustomError

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
    """A mobilizer's login, added by the campaign's manager or its candidate.

    A manager signs up for themselves, and an aspirant is named when the campaign
    is set up, so neither is made here.
    """

    username: str = Field(min_length=3, max_length=150, pattern=r"^[A-Za-z0-9._-]+$")
    role: Literal[UserRole.MOBILIZER]
    first_name: str = Field(default="", max_length=150)
    last_name: str = Field(default="", max_length=150)
    phone: str = Field(default="", max_length=20)
    email: str = Field(default="", max_length=254)

    # Required: without them the mobilizer signs in to an empty app.
    campaign: uuid.UUID | None = None
    ward: uuid.UUID | None = None
    registration_centre: uuid.UUID | None = None

    @field_validator("role", mode="before")
    @classmethod
    def _only_a_mobilizer(cls, value: object) -> object:
        if value != UserRole.MOBILIZER.value:
            raise PydanticCustomError(
                "role",
                "Only a mobilizer is added to a campaign. A manager signs up for "
                "themselves, and an aspirant is named when the campaign is set up.",
            )
        return value


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
