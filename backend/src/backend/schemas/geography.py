"""The geographic models in a response, each carrying its parent's id and name."""

import uuid
from decimal import Decimal

from pydantic import AliasPath, Field

from backend.schemas.common import ORMModel


class CountyRead(ORMModel):
    id: uuid.UUID
    name: str
    code: str
    registered_voters: int | None
    turnout_2022_pct: Decimal | None


class ConstituencyRead(ORMModel):
    id: uuid.UUID
    county: uuid.UUID = Field(validation_alias="county_id")
    county_name: str = Field(validation_alias=AliasPath("county", "name"))
    name: str
    code: str


class WardRead(ORMModel):
    id: uuid.UUID
    constituency: uuid.UUID = Field(validation_alias="constituency_id")
    constituency_name: str = Field(validation_alias=AliasPath("constituency", "name"))
    name: str
    code: str
    registered_voters: int | None


class RegistrationCentreRead(ORMModel):
    id: uuid.UUID
    ward: uuid.UUID = Field(validation_alias="ward_id")
    ward_name: str = Field(validation_alias=AliasPath("ward", "name"))
    code: str
    name: str
    registered_voters: int | None


class PollingStationRead(ORMModel):
    id: uuid.UUID
    ward: uuid.UUID = Field(validation_alias="ward_id")
    centre_code: str
    centre_name: str
    code: str
    name: str
    registered_voters: int | None
