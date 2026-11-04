"""The party's settings as the public site reads them and the console writes them."""

import re
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
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
from backend.services.branding import INK, MIN_CONTRAST, WHITE, contrast
from backend.services.consent import PARTY_WORDING, SUBSCRIBE_WORDING, VOLUNTEER_WORDING

COLOUR = re.compile(r"^#[0-9a-fA-F]{6}$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _colour(value: str) -> str:
    if not COLOUR.match(value):
        raise ValueError("Use a colour like #1f2937.")
    return value.lower()


def _link(value: str) -> str:
    if value and not value.startswith(("http://", "https://", "/static/")):
        raise ValueError("Use a web address starting with http:// or https://.")
    if value.startswith("/static/") and ".." in value:
        raise ValueError("Use a file under /static/.")
    return value


def _email(value: str) -> str:
    if value and not EMAIL.match(value):
        raise ValueError("Use an email address like name@example.com.")
    return value


Colour = Annotated[str, Field(max_length=7), AfterValidator(_colour)]
Link = Annotated[str, Field(max_length=500), AfterValidator(_link)]
Email = Annotated[str, Field(max_length=254), AfterValidator(_email)]


class PartySettingsRead(ORMModel):
    name: str
    short_name: str
    slogan: str
    registration_number: str
    about_headline: str
    founded_year: str
    logo_url: str
    primary_colour: str
    secondary_colour: str
    contact_email: str
    contact_phone: str
    address: str
    description: str
    manifesto_text: str
    manifesto_url: str
    aspirant_steps: str
    social_links: dict[str, str]
    privacy_notice: str
    privacy_notice_version: str
    updated_at: datetime
    # The forms' consent labels; the server records these same texts.
    consent_wording: str = PARTY_WORDING[PartyConsentChannel.WEB_FORM]
    volunteer_consent_wording: str = VOLUNTEER_WORDING
    subscribe_consent_wording: str = SUBSCRIBE_WORDING


class PartySettingsUpdate(WriteModel):
    """Every editable field; the request replaces the whole row."""

    name: str = Field(min_length=1, max_length=150)
    short_name: str = Field(default="", max_length=30)
    slogan: str = Field(default="", max_length=150)
    registration_number: str = Field(default="", max_length=40)
    about_headline: str = Field(default="", max_length=150)
    founded_year: str = Field(default="", pattern=r"^(\d{4})?$")
    logo_url: Link = ""
    primary_colour: Colour
    secondary_colour: Colour
    contact_email: Email = ""
    contact_phone: str = Field(default="", max_length=20)
    address: str = Field(default="", max_length=300)
    description: str = ""
    manifesto_text: str = ""
    manifesto_url: Link = ""
    aspirant_steps: str = Field(default="", max_length=20000)
    social_links: dict[Annotated[str, Field(max_length=40)], Link] = Field(default_factory=dict)
    privacy_notice: str = Field(default="", max_length=20000)
    privacy_notice_version: str = Field(default="1", min_length=1, max_length=20)

    @model_validator(mode="after")
    def _plain(self) -> "PartySettingsUpdate":
        for name in (
            "name",
            "short_name",
            "slogan",
            "registration_number",
            "about_headline",
            "logo_url",
            "contact_email",
            "contact_phone",
            "privacy_notice_version",
        ):
            plain_text(getattr(self, name))
        # Buttons put white text on the primary colour and ink text on the secondary.
        if contrast(self.primary_colour, WHITE) < MIN_CONTRAST:
            raise ValueError("The primary colour is too light for white text; pick a darker one.")
        if contrast(self.secondary_colour, INK) < MIN_CONTRAST:
            raise ValueError("The secondary colour is too dark for ink text; pick a lighter one.")
        for name in (
            "address",
            "description",
            "manifesto_text",
            "manifesto_url",
            "aspirant_steps",
            "privacy_notice",
        ):
            plain_text(getattr(self, name), lines=True)
        for key, link in self.social_links.items():
            plain_text(key)
            plain_text(link)
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


class PartyContribute(WriteModel):
    """A contribution as the Contribute page takes it."""

    amount_kes: int = Field(ge=10, le=1_000_000)
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
    phone: str = Field(min_length=1, max_length=20)
    consent_given: StrictBool

    @field_validator("name", "phone")
    @classmethod
    def _plain(cls, value: str) -> str:
        return plain_text(value)

    @field_validator("consent_given")
    @classmethod
    def _consent_is_required(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Tick the box to confirm the contribution is your own.")
        return value


class PartyContributed(BaseModel):
    demo: bool
    message: str


class PartyStats(BaseModel):
    """Counts the About page shows."""

    members: int
    branches: int
