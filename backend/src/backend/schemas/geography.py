"""What the geographic models look like in a response.

Each schema carries its parent's id rather than a nested parent object.
"""

import uuid
from decimal import Decimal

from backend.schemas.common import ORMModel


class CountyRead(ORMModel):
    id: uuid.UUID
    name: str
    code: str
    registered_voters: int | None
    turnout_2022_pct: Decimal | None


class ConstituencyRead(ORMModel):
    id: uuid.UUID
    county_id: uuid.UUID
    name: str
    code: str


class WardRead(ORMModel):
    id: uuid.UUID
    constituency_id: uuid.UUID
    name: str
    code: str
    registered_voters: int | None


class RegistrationCentreRead(ORMModel):
    id: uuid.UUID
    ward_id: uuid.UUID
    code: str
    name: str
    registered_voters: int | None


class PollingStationRead(ORMModel):
    id: uuid.UUID
    ward_id: uuid.UUID
    centre_code: str
    centre_name: str
    code: str
    name: str
    registered_voters: int | None
