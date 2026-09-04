"""Every model, imported here so `Base.metadata` holds the full schema."""

from backend.db.base import Base
from backend.models.auth_token import AuthToken
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
    "AuthToken",
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
