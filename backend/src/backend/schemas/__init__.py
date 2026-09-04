"""The request and response schemas, one module per resource."""

from backend.schemas.auth import LoginRequest, LoginResponse, LoginUser
from backend.schemas.campaign import (
    CampaignRead,
    CampaignSetup,
    CampaignSetupResponse,
    EventCreate,
    EventInvite,
    EventInviteResult,
    EventRead,
    EventRecord,
    InviteRecipient,
    MobilizerCreate,
    MobilizerRead,
    SetupSummary,
    SupporterCreate,
    SupporterRead,
    TargetCreate,
    TargetRead,
    TargetUpdate,
)
from backend.schemas.common import ORMModel
from backend.schemas.geography import (
    ConstituencyRead,
    CountyRead,
    PollingStationRead,
    RegistrationCentreRead,
    WardRead,
)
from backend.schemas.user import UserCreate, UserCreated, UserRead

__all__ = [
    "CampaignRead",
    "CampaignSetup",
    "CampaignSetupResponse",
    "ConstituencyRead",
    "CountyRead",
    "EventCreate",
    "EventInvite",
    "EventInviteResult",
    "EventRead",
    "EventRecord",
    "InviteRecipient",
    "LoginRequest",
    "LoginResponse",
    "LoginUser",
    "MobilizerCreate",
    "MobilizerRead",
    "ORMModel",
    "PollingStationRead",
    "RegistrationCentreRead",
    "SetupSummary",
    "SupporterCreate",
    "SupporterRead",
    "TargetCreate",
    "TargetRead",
    "TargetUpdate",
    "UserCreate",
    "UserCreated",
    "UserRead",
    "WardRead",
]
