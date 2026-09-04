"""Base classes for the request and response schemas."""

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    # from_attributes reads a SQLAlchemy object; populate_by_name allows
    # constructing by field name rather than alias.
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, extra="forbid")


class WriteModel(BaseModel):
    """A request body. An unknown field is an error, not something ignored."""

    model_config = ConfigDict(extra="forbid")
