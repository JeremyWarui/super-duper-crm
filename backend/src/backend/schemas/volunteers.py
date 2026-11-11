"""Volunteer register schemas for membership officers."""

import uuid
from datetime import datetime
from typing import Literal

from backend.models import ContactMethod, PartyMemberStatus, Profession, VolunteerStatus
from backend.schemas.common import ORMModel, Page, WriteModel, plain_lines
from backend.schemas.party import MemberPlace


class VolunteerRead(ORMModel):
    """A volunteer row as the officer's list shows it."""

    # The volunteer profile's own details were erased; the member's stay while they are one.
    erased_at: datetime | None = None

    id: uuid.UUID
    member_id: uuid.UUID
    full_name: str
    phone: str
    ward: MemberPlace
    constituency: MemberPlace
    county: MemberPlace
    registration_centre: MemberPlace | None
    profession: Profession | None
    profession_other: str
    status: VolunteerStatus
    interests: list[str]
    interest_other: str
    preferred_contact: ContactMethod
    availability_notes: str | None
    member_status: PartyMemberStatus
    created_at: datetime


VolunteerPage = Page[VolunteerRead]


class VolunteerUpdate(WriteModel):
    """An officer's change: a move between active and inactive, and the availability notes."""

    status: Literal["active", "inactive"] | None = None
    availability_notes: plain_lines(2000) | None = None
