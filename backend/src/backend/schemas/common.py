"""Base classes for the request and response schemas."""

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    # from_attributes lets Model.model_validate() read a SQLAlchemy object.
    # populate_by_name lets Python construct one by field name, where reading a
    # model object goes through the aliases instead.
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, extra="forbid")


class WriteModel(BaseModel):
    """A request body. An unknown field is an error, not something ignored.

    Silently dropping it would let a client believe it had set a value that the
    server never read, such as a win number it is not allowed to choose.
    """

    model_config = ConfigDict(extra="forbid")
