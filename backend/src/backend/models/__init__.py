"""Every model, imported here so `Base.metadata` holds the full schema."""

from backend.db.base import Base
from backend.models.audit import AuditEvent
from backend.models.auth_token import AuthToken
from backend.models.campaign import Campaign
from backend.models.enums import (
    ConsentChannel,
    ContactMethod,
    EventStatus,
    LabelledStrEnum,
    OfficeLevel,
    OperationalGrain,
    PartyConsentChannel,
    PartyMemberStatus,
    PartyRequestKind,
    PartyRoleName,
    PaymentStatus,
    Seat,
    SupportLevel,
    UserRole,
    VolunteerInterest,
    VolunteerStatus,
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
from backend.models.party import (
    PartyMember,
    PartyRequest,
    PartyRole,
    PartySettings,
    VolunteerProfile,
)
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
    "ContactMethod",
    "OperationalGrain",
    "PartyConsentChannel",
    "PartyMember",
    "PartyRequest",
    "PartyRequestKind",
    "PartyMemberStatus",
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
    "VolunteerInterest",
    "VolunteerProfile",
    "VolunteerStatus",
    "UserRole",
    "Ward",
    "compute_win_number",
    "unit_key",
]
