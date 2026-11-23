"""The public website's forms: volunteering, news sign-ups, and their answers."""

from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from backend.models import ContactMethod, Profession, VolunteerArea
from backend.schemas.common import WriteModel, consent, plain_text

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=75)]
OtherText = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=100), AfterValidator(plain_text)
]
PlainName = Annotated[Name, AfterValidator(plain_text)]


class VolunteerPart(WriteModel):
    """The volunteer form's profession, how they would like to help, and consent."""

    profession: Profession
    profession_other: OtherText = ""
    areas: Annotated[list[VolunteerArea], Field(min_length=1)]
    area_other: OtherText = ""
    preferred_contact: ContactMethod
    consent_given: consent("Consent is required before the campaign can contact you.", strict=True)

    @field_validator("areas")
    @classmethod
    def _no_duplicates(cls, value: list[VolunteerArea]) -> list[VolunteerArea]:
        if len(set(value)) != len(value):
            raise ValueError("List each area once.")
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


class Received(BaseModel):
    message: str


class Subscribe(WriteModel):
    """A footer sign-up: a Kenyan mobile number or an email address."""

    contact: str = Field(min_length=1, max_length=254)
    consent_given: consent("Tick the box to agree to receive our news.", strict=True)

    @field_validator("contact")
    @classmethod
    def _plain(cls, value: str) -> str:
        return plain_text(value.strip())


class Subscribed(BaseModel):
    message: str
    unsubscribe_url: str
