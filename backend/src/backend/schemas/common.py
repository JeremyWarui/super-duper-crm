"""Base classes shared by the request and response schemas."""

import uuid

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, extra="forbid")


class WriteModel(BaseModel):
    """A request body; an unknown field is an error."""

    model_config = ConfigDict(extra="forbid")


class LoginDetails(WriteModel):
    """Who a new login is for."""

    username: str = Field(min_length=3, max_length=150, pattern=r"^[A-Za-z0-9._-]+$")
    first_name: str = Field(default="", max_length=150)
    last_name: str = Field(default="", max_length=150)
    phone: str = Field(default="", max_length=20)
    email: str = Field(default="", max_length=254)


class NewLogin(ORMModel):
    """A login just created; `password` is shown this once."""

    id: uuid.UUID
    username: str
    full_name: str
    password: str
