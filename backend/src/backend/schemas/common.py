"""Shared base for read schemas.

`from_attributes` is what lets `Model.model_validate(orm_object)` walk a
SQLAlchemy instance. Only read (output) schemas exist so far: create and update
schemas describe request bodies, and there are no endpoints yet to receive them.
"""

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
