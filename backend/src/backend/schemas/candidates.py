"""The candidate page as the website shows it and the website editor writes it, and the
volunteers it signs up for the campaign."""

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field

from backend.models import ContactMethod, Profession, Seat, VolunteerStatus
from backend.schemas.common import (
    Erasable,
    Named,
    ORMModel,
    WriteModel,
    plain_lines,
    plain_text,
    trimmed,
)
from backend.schemas.content import Image, RichBody
from backend.schemas.site import Email
from backend.schemas.website import PlainName, VolunteerPart


class Priority(WriteModel):
    title: Annotated[str, Field(min_length=1, max_length=80), AfterValidator(plain_text)]
    text: Annotated[str, Field(max_length=300), AfterValidator(plain_text)] = ""
    image_url: Image = ""


class ProfileWrite(WriteModel):
    """The whole profile; the request replaces it."""

    photo_url: Image = ""
    slogan: trimmed(120) = ""
    bio: RichBody = ""
    priorities: Annotated[list[Priority], Field(max_length=3)] = []
    office_address: trimmed(300) = ""
    office_phone: trimmed(20) = ""
    office_email: Email = ""
    published: bool = False


class ProfileRead(BaseModel):
    photo_url: str = ""
    slogan: str = ""
    bio: str = ""
    priorities: list[Priority] = []
    office_address: str = ""
    office_phone: str = ""
    office_email: str = ""
    published: bool = False


class CandidateCard(BaseModel):
    slug: str
    name: str
    seat: Seat
    area: str
    county: str
    photo_url: str
    slogan: str


class CandidateEvent(BaseModel):
    id: uuid.UUID
    title: str
    event_date: date
    venue: str


class CandidateDetail(CandidateCard):
    bio: str
    priorities: list[Priority]
    office_address: str
    office_phone: str
    office_email: str
    events: list[CandidateEvent]
    # True while the page takes volunteers.
    volunteering_open: bool
    wards: list[Named]
    # The form's consent label; the server records this same text.
    consent_wording: str


class CandidateVolunteerCreate(VolunteerPart):
    """The volunteer form: how they would like to help, plus who and where."""

    first_name: PlainName
    last_name: PlainName
    email: Email = Field(min_length=3)
    phone: str = Field(min_length=9, max_length=20)
    ward: uuid.UUID
    registration_centre: uuid.UUID


class CampaignVolunteerRead(Erasable, ORMModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    phone: str
    email: str | None
    ward: Named
    registration_centre: Named | None
    profession: Profession | None
    profession_other: str
    status: VolunteerStatus
    interests: list[str]
    interest_other: str
    preferred_contact: ContactMethod
    availability_notes: str | None
    created_at: datetime


class CampaignVolunteerUpdate(WriteModel):
    """The manager's change: active or inactive, and notes."""

    status: Literal["active", "inactive"] | None = None
    availability_notes: plain_lines(2000) | None = None
