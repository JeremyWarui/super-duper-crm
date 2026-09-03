"""Base class for the read schemas."""

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    # from_attributes lets Model.model_validate() read a SQLAlchemy object.
    model_config = ConfigDict(from_attributes=True, extra="forbid")
