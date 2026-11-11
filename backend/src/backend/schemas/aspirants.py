"""Nominations as the nominations officer reads and writes them."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel

from backend.models import AspirantStatus, Seat
from backend.schemas.admin import AdminUserCreated
from backend.schemas.campaign import SetupSummary
from backend.schemas.common import (
    CampaignTitle,
    LoginDetails,
    ORMModel,
    Page,
    WriteModel,
    plain_lines,
)
from backend.schemas.party import MemberPlace


class CandidateRead(ORMModel):
    """An approved member who can be nominated; never their phone."""

    id: uuid.UUID
    full_name: str
    email: str | None = None
    ward: MemberPlace


class AspirantArea(BaseModel):
    level: str
    id: uuid.UUID
    name: str


class AspirantRead(ORMModel):
    id: uuid.UUID
    member: CandidateRead
    seat: Seat
    area: AspirantArea
    status: AspirantStatus
    status_reason: str | None
    decided_at: datetime | None
    campaign_id: uuid.UUID | None
    created_at: datetime
    # A member's own application; blank for an officer's nomination.
    window_title: str | None = None
    fee_kes: int = 0
    fee_paid_at: datetime | None = None
    fee_reference: str = ""
    declared_at: datetime | None = None
    documents: list["DocumentRead"] = []


class DocumentRead(BaseModel):
    id: uuid.UUID
    label: str


AspirantPage = Page[AspirantRead]


class AspirantCreate(WriteModel):
    member: uuid.UUID
    seat: Seat
    county: uuid.UUID | None = None
    constituency: uuid.UUID | None = None
    ward: uuid.UUID | None = None


class AspirantMove(WriteModel):
    status: AspirantStatus
    reason: plain_lines(1000) | None = None


class WorkspaceCreate(WriteModel):
    """An approved aspirant's campaign: its title and date, and its new logins."""

    title: CampaignTitle | None = None
    election_date: date | None = None
    candidate: LoginDetails
    manager: LoginDetails | None = None


class WorkspaceCreated(BaseModel):
    """`logins` say how each invite link went out."""

    aspirant: AspirantRead
    setup: SetupSummary
    logins: list[AdminUserCreated]
