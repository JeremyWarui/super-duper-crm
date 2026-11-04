"""Candidate profiles as the website shows them and the website editor writes them, and the
volunteers a candidate's page signs up for that candidate's campaign."""

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, field_validator

from backend.models import ContactMethod, Profession, Seat, VolunteerStatus
from backend.schemas.common import ORMModel, WriteModel, plain_text
from backend.schemas.content import Image
from backend.schemas.party import MemberPlace, Name, VolunteerPart
from backend.schemas.site import Email


def _line(limit: int):
    return Annotated[str, Field(max_length=limit), AfterValidator(lambda v: plain_text(v).strip())]


class Priority(WriteModel):
    title: Annotated[str, Field(min_length=1, max_length=80), AfterValidator(plain_text)]
    text: Annotated[str, Field(max_length=300), AfterValidator(plain_text)] = ""


class ProfileWrite(WriteModel):
    """The whole profile; the request replaces it."""

    photo_url: Image = ""
    slogan: _line(120) = ""
    bio: Annotated[
        str, Field(max_length=2000), AfterValidator(lambda v: plain_text(v, lines=True))
    ] = ""
    priorities: Annotated[list[Priority], Field(max_length=3)] = []
    office_address: _line(300) = ""
    office_phone: _line(20) = ""
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


class CandidateAdminRead(BaseModel):
    """An approved aspirant for the website editor, with the profile written so far."""

    aspirant_id: uuid.UUID
    name: str
    seat: Seat
    area: str
    profile: ProfileRead


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
    # True when the aspirant has a campaign; the support form shows only then.
    volunteering_open: bool
    wards: list[MemberPlace]
    # The form's consent label; the server records this same text.
    consent_wording: str


class PostAspirants(WriteModel):
    aspirant_ids: Annotated[list[uuid.UUID], Field(max_length=50)]


class CandidateVolunteerCreate(VolunteerPart):
    """The "Support <name>" form: the join's volunteer section plus who and where."""

    first_name: Name
    last_name: Name
    email: Email = Field(min_length=3)
    phone: str = Field(min_length=9, max_length=20)
    ward: uuid.UUID
    registration_centre: uuid.UUID

    @field_validator("first_name", "last_name")
    @classmethod
    def _plain_name(cls, value: str) -> str:
        return plain_text(value)


class CampaignVolunteerRead(ORMModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    phone: str
    email: str | None
    ward: MemberPlace
    registration_centre: MemberPlace | None
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
    availability_notes: str | None = Field(default=None, max_length=2000)

    @field_validator("availability_notes")
    @classmethod
    def _plain(cls, value: str | None) -> str | None:
        return plain_text(value, lines=True)
