"""Base class for the read schemas."""

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    # from_attributes lets Model.model_validate() read a SQLAlchemy object.
    # populate_by_name lets Python construct one by field name, where reading a
    # model object goes through the aliases instead.
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, extra="forbid")
