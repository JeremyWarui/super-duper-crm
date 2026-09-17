"""Mobilizer logins created from inside a campaign."""

import uuid
from typing import Literal

from pydantic import field_validator
from pydantic_core import PydanticCustomError

from backend.models.enums import UserRole
from backend.schemas.common import LoginDetails, NewLogin


class UserCreate(LoginDetails):
    role: Literal[UserRole.MOBILIZER]
    campaign: uuid.UUID
    ward: uuid.UUID
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


class UserCreated(NewLogin):
    role: UserRole
    phone: str
    mobilizer: uuid.UUID
    ward_name: str
