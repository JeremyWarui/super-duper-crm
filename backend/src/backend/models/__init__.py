"""Every mapped class, imported here so `Base.metadata` is complete.

Alembic and `create_all` both need one module that pulls in the whole mapping;
a class missing from this file silently stops being migrated.
"""

from backend.db.base import Base
from backend.models.campaign import Campaign
from backend.models.enums import (
    EventStatus,
    LabelledStrEnum,
    OfficeLevel,
    OperationalGrain,
    SupportLevel,
    UserRole,
)
from backend.models.event import Event
from backend.models.geography import (
    Constituency,
    County,
    PollingStation,
    RegistrationCentre,
    Ward,
)
from backend.models.mobilizer import Mobilizer
from backend.models.supporter import Supporter
from backend.models.target import Target, compute_win_number
from backend.models.user import User

__all__ = [
    "Base",
    "Campaign",
    "Constituency",
    "County",
    "Event",
    "EventStatus",
    "LabelledStrEnum",
    "Mobilizer",
    "OfficeLevel",
    "OperationalGrain",
    "PollingStation",
    "RegistrationCentre",
    "SupportLevel",
    "Supporter",
    "Target",
    "User",
    "UserRole",
    "Ward",
    "compute_win_number",
]
