"""Every model, imported here so `Base.metadata` holds the full schema."""

from backend.db.base import Base
from backend.models.assignment import Assignment
from backend.models.audit import AuditEvent
from backend.models.auth_token import AuthToken
from backend.models.campaign import Campaign
from backend.models.content import (
    AgendaIssue,
    CandidateProfile,
    Document,
    HeroSlide,
    Post,
    Subscriber,
    Video,
)
from backend.models.enums import (
    AgentStatus,
    AssignmentKind,
    AssignmentStatus,
    ConsentChannel,
    ContactMethod,
    DataRequestKind,
    DataRequestStatus,
    EventStatus,
    FieldRole,
    FileArea,
    LabelledStrEnum,
    LinkPurpose,
    OfficeLevel,
    OperationalGrain,
    PayInMethod,
    PayInStatus,
    PaymentStatus,
    PostKind,
    PostLabel,
    Profession,
    RegistrationStatus,
    Seat,
    SupportLevel,
    UserRole,
    VolunteerArea,
    VolunteerStatus,
)
from backend.models.event import Event
from backend.models.files import StoredFile
from backend.models.geography import (
    Constituency,
    County,
    RegistrationCentre,
    Ward,
)
from backend.models.imports import BackupRun, ImportChange, ImportRun
from backend.models.login import EmailLog, LoginInvite
from backend.models.membership import CampaignMember, CampaignMemberArea
from backend.models.mobilizer import Mobilizer
from backend.models.payin import PaymentIn
from backend.models.payment import Payment, ReconcileDifference, ReconcileRun
from backend.models.privacy import DataRequest
from backend.models.site import SetupToken, SiteSettings
from backend.models.sms import CampaignMessage, SmsInbound, SmsLog, SmsOptOut
from backend.models.supporter import Supporter
from backend.models.target import Target, compute_win_number, unit_key
from backend.models.team import Agent, TeamRegistration
from backend.models.user import User
from backend.models.volunteer import VolunteerProfile

__all__ = [
    "DataRequest",
    "DataRequestKind",
    "DataRequestStatus",
    "CampaignMessage",
    "SmsInbound",
    "SmsLog",
    "PaymentIn",
    "PayInMethod",
    "PayInStatus",
    "SmsOptOut",
    "ReconcileDifference",
    "ReconcileRun",
    "FileArea",
    "AuditEvent",
    "AgendaIssue",
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
    "Agent",
    "Assignment",
    "AssignmentKind",
    "AssignmentStatus",
    "AgentStatus",
    "EmailLog",
    "FieldRole",
    "RegistrationStatus",
    "TeamRegistration",
    "LinkPurpose",
    "LoginInvite",
    "OperationalGrain",
    "Post",
    "Payment",
    "PaymentStatus",
    "PostKind",
    "PostLabel",
    "Document",
    "CandidateProfile",
    "Video",
    "Seat",
    "BackupRun",
    "ImportChange",
    "ImportRun",
    "SetupToken",
    "SiteSettings",
    "StoredFile",
    "RegistrationCentre",
    "SupportLevel",
    "Subscriber",
    "Supporter",
    "Target",
    "User",
    "VolunteerArea",
    "VolunteerProfile",
    "VolunteerStatus",
    "UserRole",
    "Ward",
    "compute_win_number",
    "unit_key",
]
