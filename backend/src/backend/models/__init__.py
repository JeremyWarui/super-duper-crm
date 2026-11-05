"""Every model, imported here so `Base.metadata` holds the full schema."""

from backend.db.base import Base
from backend.models.audit import AuditEvent
from backend.models.auth_token import AuthToken
from backend.models.campaign import Campaign
from backend.models.content import (
    AgendaIssue,
    Branch,
    CandidateProfile,
    HeroSlide,
    PartyDocument,
    PartyLeader,
    PartyOrgan,
    PartyPost,
    PartyValue,
    PartyVideo,
    PrimaryResult,
    Subscriber,
    party_post_aspirants,
)
from backend.models.enums import (
    AspirantStatus,
    ConsentChannel,
    ContactMethod,
    EventStatus,
    LabelledStrEnum,
    OfficeLevel,
    OperationalGrain,
    OrganisationType,
    PartyConsentChannel,
    PartyMemberStatus,
    PartyRequestKind,
    PartyRoleName,
    PaymentStatus,
    PostKind,
    PostLabel,
    Profession,
    Seat,
    SupportLevel,
    UserKind,
    UserRole,
    VolunteerArea,
    VolunteerStatus,
    WorkspaceKind,
)
from backend.models.event import Event
from backend.models.geography import (
    Constituency,
    County,
    RegistrationCentre,
    Ward,
)
from backend.models.membership import CampaignMember, CampaignMemberArea
from backend.models.mobilizer import Mobilizer
from backend.models.party import (
    Aspirant,
    PartyMember,
    PartyRequest,
    PartyRole,
    PartySettings,
    RecruitmentCode,
)
from backend.models.payment import Payment
from backend.models.site import SiteSettings
from backend.models.supporter import Supporter
from backend.models.target import Target, compute_win_number, unit_key
from backend.models.user import User
from backend.models.volunteer import VolunteerProfile

__all__ = [
    "Aspirant",
    "AspirantStatus",
    "AuditEvent",
    "AgendaIssue",
    "Branch",
    "HeroSlide",
    "AuthToken",
    "Base",
    "Campaign",
    "CampaignMember",
    "CampaignMemberArea",
    "Constituency",
    "County",
    "Event",
    "EventStatus",
    "LabelledStrEnum",
    "Mobilizer",
    "OfficeLevel",
    "ConsentChannel",
    "ContactMethod",
    "Profession",
    "OperationalGrain",
    "OrganisationType",
    "PartyConsentChannel",
    "PartyLeader",
    "PartyMember",
    "PartyPost",
    "PartyRequest",
    "PartyRequestKind",
    "PartyMemberStatus",
    "PartyRole",
    "PartyRoleName",
    "PartySettings",
    "RecruitmentCode",
    "Payment",
    "PaymentStatus",
    "PostKind",
    "PostLabel",
    "PartyDocument",
    "PartyOrgan",
    "PartyValue",
    "CandidateProfile",
    "party_post_aspirants",
    "PartyVideo",
    "PrimaryResult",
    "Seat",
    "SiteSettings",
    "RegistrationCentre",
    "SupportLevel",
    "Subscriber",
    "Supporter",
    "Target",
    "User",
    "VolunteerArea",
    "VolunteerProfile",
    "VolunteerStatus",
    "UserKind",
    "UserRole",
    "WorkspaceKind",
    "Ward",
    "compute_win_number",
    "unit_key",
]
