"""The party workspace as the party office and its coordinators see it."""

import uuid

from pydantic import BaseModel

from backend.models.enums import PartyMemberStatus
from backend.schemas.common import Invite, LoginDetails


class PartyWorkspaceRead(BaseModel):
    """`id` is None until the workspace is created."""

    id: uuid.UUID | None = None
    title: str = ""
    managers: list[str] = []


class PartyWorkspaceCreate(BaseModel):
    manager: LoginDetails


class PartyWorkspaceManager(BaseModel):
    manager: LoginDetails


class PartyWorkspaceCreated(BaseModel):
    """`invite` says how the Workspace Manager's invite link went out."""

    id: uuid.UUID
    title: str
    units: int
    username: str
    invite: Invite


class AreaMember(BaseModel):
    """A party member as a coordinator sees them: no consent, email or codes."""

    id: uuid.UUID
    full_name: str
    phone: str
    status: PartyMemberStatus
    ward: uuid.UUID
    ward_name: str
    registration_centre: uuid.UUID | None
    registration_centre_name: str


class AreaMembers(BaseModel):
    total: int
    page: int
    page_size: int
    members: list[AreaMember]


class Recruitment(BaseModel):
    """The coordinator's link code, and their applicants by status."""

    code: str
    by_status: dict[PartyMemberStatus, int]
