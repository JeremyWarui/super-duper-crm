"""Every model, imported here so `Base.metadata` holds the full schema."""

from backend.db.base import Base
from backend.models.audit import AuditEvent
from backend.models.auth_token import AuthToken
from backend.models.campaign import Campaign
from backend.models.enums import (
    ConsentChannel,
    EventStatus,
    LabelledStrEnum,
    OfficeLevel,
    OperationalGrain,
    PartyRoleName,
    PaymentStatus,
    Seat,
    SupportLevel,
    UserRole,
)
from backend.models.event import Event
from backend.models.geography import (
    Constituency,
    County,
    RegistrationCentre,
    Ward,
)
from backend.models.membership import CampaignMember
from backend.models.mobilizer import Mobilizer
from backend.models.party import PartyRole, PartySettings
from backend.models.payment import Payment
from backend.models.supporter import Supporter
from backend.models.target import Target, compute_win_number, unit_key
from backend.models.user import User

__all__ = [
    "AuditEvent",
    "AuthToken",
    "Base",
    "Campaign",
    "CampaignMember",
    "Constituency",
    "County",
    "Event",
    "EventStatus",
    "LabelledStrEnum",
    "Mobilizer",
    "OfficeLevel",
    "ConsentChannel",
    "OperationalGrain",
    "PartyRole",
    "PartyRoleName",
    "PartySettings",
    "Payment",
    "PaymentStatus",
    "Seat",
    "RegistrationCentre",
    "SupportLevel",
    "Supporter",
    "Target",
    "User",
    "UserRole",
    "Ward",
    "compute_win_number",
    "unit_key",
]
