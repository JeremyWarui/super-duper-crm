"""The site settings as the public site reads them and the console writes them."""

import re
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, Field, model_validator

from backend.models import OrganisationType
from backend.schemas.common import ORMModel, WriteModel, plain_text
from backend.services.branding import INK, MIN_CONTRAST, WHITE, contrast
from backend.services.consent import VOLUNTEER_WORDING, subscribe_wording

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


def email_address(value: str) -> str:
    if value and not EMAIL.match(value):
        raise ValueError("Use an email address like name@example.com.")
    return value


Colour = Annotated[str, Field(max_length=7), AfterValidator(_colour)]
Link = Annotated[str, Field(max_length=500), AfterValidator(_link)]
Email = Annotated[str, Field(max_length=254), AfterValidator(email_address)]


def refuse_low_contrast(primary: str, secondary: str) -> None:
    """Buttons put white text on the primary colour and ink text on the secondary."""
    if contrast(primary, WHITE) < MIN_CONTRAST:
        raise ValueError("The primary colour is too light for white text; pick a darker one.")
    if contrast(secondary, INK) < MIN_CONTRAST:
        raise ValueError("The secondary colour is too dark for ink text; pick a lighter one.")


class SiteIdentity(WriteModel):
    """The name, colours, contacts and privacy notice that setup and the console both write."""

    name: str = Field(min_length=1, max_length=150)
    short_name: str = Field(default="", max_length=30)
    primary_colour: Colour
    secondary_colour: Colour
    contact_email: Email = ""
    contact_phone: str = Field(default="", max_length=20)
    address: str = Field(default="", max_length=300)
    privacy_notice: str = Field(default="", max_length=20000)


class SiteSettingsRead(ORMModel):
    organisation_type: OrganisationType
    name: str
    short_name: str
    slogan: str
    about_headline: str
    logo_url: str
    primary_colour: str
    secondary_colour: str
    contact_email: str
    contact_phone: str
    address: str
    social_links: dict[str, str]
    description: str
    manifesto_text: str
    manifesto_url: str
    privacy_notice: str
    privacy_notice_version: str
    payment_instructions: str
    mpesa_paybill: str = ""
    mpesa_account: str = ""
    mpesa_till: str = ""
    updated_at: datetime
    # The forms' consent labels; the server records these same texts.
    volunteer_consent_wording: str = VOLUNTEER_WORDING
    subscribe_consent_wording: str = ""

    @model_validator(mode="after")
    def _wording(self) -> "SiteSettingsRead":
        self.subscribe_consent_wording = subscribe_wording(self.organisation_type)
        return self


class SiteSettingsUpdate(SiteIdentity):
    """Every editable field except the organisation type; the request replaces the whole row."""

    slogan: str = Field(default="", max_length=150)
    about_headline: str = Field(default="", max_length=150)
    logo_url: Link = ""
    social_links: dict[Annotated[str, Field(max_length=40)], Link] = Field(default_factory=dict)
    description: str = ""
    manifesto_text: str = ""
    manifesto_url: Link = ""
    privacy_notice_version: str = Field(default="1", min_length=1, max_length=20)
    payment_instructions: str = Field(default="", max_length=2000)
    mpesa_paybill: str = Field(default="", pattern=r"^(\d{5,7})?$")
    mpesa_account: str = Field(default="", max_length=20)
    mpesa_till: str = Field(default="", pattern=r"^(\d{5,7})?$")

    @model_validator(mode="after")
    def _plain(self) -> "SiteSettingsUpdate":
        for name in (
            "name",
            "short_name",
            "slogan",
            "about_headline",
            "logo_url",
            "contact_email",
            "contact_phone",
            "privacy_notice_version",
            "mpesa_account",
        ):
            plain_text(getattr(self, name))
        if self.mpesa_paybill and self.mpesa_till:
            raise ValueError("Give a Paybill or a Till, not both.")
        refuse_low_contrast(self.primary_colour, self.secondary_colour)
        for name in (
            "address",
            "description",
            "manifesto_text",
            "manifesto_url",
            "privacy_notice",
            "payment_instructions",
        ):
            plain_text(getattr(self, name), lines=True)
        for key, link in self.social_links.items():
            plain_text(key)
            plain_text(link)
        return self
