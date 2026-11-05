"""The party office's settings, members and volunteers, as the API reads and writes them."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    Field,
    StrictBool,
    StringConstraints,
    field_validator,
    model_validator,
)

from backend.models import (
    ContactMethod,
    PartyConsentChannel,
    PartyMemberStatus,
    Profession,
    VolunteerArea,
)
from backend.schemas.common import ORMModel, WriteModel, plain_text
from backend.schemas.site import Email
from backend.services.consent import PARTY_WORDING


class PartySettingsRead(ORMModel):
    registration_number: str
    founded_year: str
    aspirant_steps: str
    updated_at: datetime
    # The join form's consent label; the server records this same text.
    consent_wording: str = PARTY_WORDING[PartyConsentChannel.WEB_FORM]


class PartySettingsUpdate(WriteModel):
    """Every editable party-only field; the request replaces them all."""

    registration_number: str = Field(default="", max_length=40)
    founded_year: str = Field(default="", pattern=r"^(\d{4})?$")
    aspirant_steps: str = Field(default="", max_length=20000)

    @model_validator(mode="after")
    def _plain(self) -> "PartySettingsUpdate":
        plain_text(self.registration_number)
        plain_text(self.aspirant_steps, lines=True)
        return self


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=75)]
OtherText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]


class VolunteerPart(WriteModel):
    """The application form's volunteer section, shown by the "Volunteer for events" tick."""

    profession: Profession
    profession_other: OtherText = ""
    areas: Annotated[list[VolunteerArea], Field(min_length=1)]
    area_other: OtherText = ""
    preferred_contact: ContactMethod
    consent_given: StrictBool

    @field_validator("profession_other", "area_other")
    @classmethod
    def _plain(cls, value: str) -> str:
        return plain_text(value)

    @field_validator("areas")
    @classmethod
    def _no_duplicates(cls, value: list[VolunteerArea]) -> list[VolunteerArea]:
        if len(set(value)) != len(value):
            raise ValueError("List each area once.")
        return value

    @field_validator("consent_given")
    @classmethod
    def _consent_is_required(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Consent is required before the party can contact you.")
        return value

    @model_validator(mode="after")
    def _other_text(self) -> "VolunteerPart":
        if self.profession is Profession.OTHER:
            if not self.profession_other:
                raise ValueError("Say what your profession is.")
        else:
            self.profession_other = ""
        if VolunteerArea.OTHER in self.areas:
            if not self.area_other:
                raise ValueError("Say how else you would like to help.")
        else:
            self.area_other = ""
        return self


class PartyJoinCreate(WriteModel):
    first_name: Name
    surname: Name
    phone: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
    email: Annotated[Email, StringConstraints(strip_whitespace=True, min_length=1)]
    password: str = Field(min_length=8, max_length=128)
    ward: uuid.UUID
    registration_centre: uuid.UUID
    consent_given: StrictBool
    volunteer: VolunteerPart | None = None
    # A coordinator's recruitment code from `/join-party?r=`; any other value is ignored.
    recruitment: str | None = Field(default=None, max_length=32)

    @field_validator("first_name", "surname", "phone", "email")
    @classmethod
    def _plain(cls, value: str) -> str:
        return plain_text(value)

    @field_validator("first_name", "surname")
    @classmethod
    def _has_a_letter(cls, value: str) -> str:
        if not any(ch.isalpha() for ch in value):
            raise ValueError("Enter your name.")
        return value

    @field_validator("consent_given")
    @classmethod
    def _consent_is_required(cls, value: bool) -> bool:
        # Data Protection Act 2019.
        if not value:
            raise ValueError("Consent is required before we can store these details.")
        return value


class PartyJoinDone(BaseModel):
    """The paths of the applicant's withdrawal pages; the volunteer one only if they volunteered."""

    withdraw_url: str
    volunteer_withdraw_url: str | None = None


class PartyWithdrawn(BaseModel):
    message: str


class PartyPlace(ORMModel):
    """A county, constituency or ward on the public application's place picker."""

    id: uuid.UUID
    name: str


class MemberPlace(ORMModel):
    id: uuid.UUID
    name: str


class MemberRead(ORMModel):
    """A register row as the officer's list shows it."""

    id: uuid.UUID
    full_name: str
    phone: str
    email: str | None
    status: PartyMemberStatus
    ward: MemberPlace
    constituency: MemberPlace
    county: MemberPlace
    created_at: datetime
    # Whether any login reaches this member's account; false when the join's email was taken.
    has_login: bool = False


class MemberDetail(MemberRead):
    status_reason: str | None
    decided_at: datetime | None
    consent_channel: PartyConsentChannel
    consent_wording: str
    consent_at: datetime


class MemberPage(BaseModel):
    total: int
    items: list[MemberRead]


class MemberMove(WriteModel):
    status: PartyMemberStatus
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("reason")
    @classmethod
    def _plain(cls, value: str | None) -> str | None:
        return plain_text(value, lines=True)


class PartySubscribe(WriteModel):
    """A footer sign-up: a Kenyan mobile number or an email address."""

    contact: str = Field(min_length=1, max_length=254)
    consent_given: StrictBool

    @field_validator("contact")
    @classmethod
    def _plain(cls, value: str) -> str:
        return plain_text(value.strip())

    @field_validator("consent_given")
    @classmethod
    def _consent_is_required(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Tick the box to agree to receive party news.")
        return value


class PartySubscribed(BaseModel):
    message: str
    unsubscribe_url: str


class PartyStats(BaseModel):
    """Counts the About page shows."""

    members: int
    branches: int
