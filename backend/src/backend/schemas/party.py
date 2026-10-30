"""The party's settings as the public site reads them and the console writes them."""

import re
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, Field

from backend.schemas.common import ORMModel, WriteModel

COLOUR = re.compile(r"^#[0-9a-fA-F]{6}$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _colour(value: str) -> str:
    if not COLOUR.match(value):
        raise ValueError("Use a colour like #1f2937.")
    return value.lower()


def _link(value: str) -> str:
    if value and not value.startswith(("http://", "https://", "/static/")):
        raise ValueError("Use a web address starting with http:// or https://.")
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
    logo_url: str
    primary_colour: str
    secondary_colour: str
    contact_email: str
    contact_phone: str
    address: str
    description: str
    manifesto_text: str
    manifesto_url: str
    social_links: dict[str, str]
    updated_at: datetime


class PartySettingsUpdate(WriteModel):
    """Every editable field; the request replaces the whole row."""

    name: str = Field(min_length=1, max_length=150)
    short_name: str = Field(default="", max_length=30)
    logo_url: Link = ""
    primary_colour: Colour
    secondary_colour: Colour
    contact_email: Email = ""
    contact_phone: str = Field(default="", max_length=20)
    address: str = Field(default="", max_length=300)
    description: str = ""
    manifesto_text: str = ""
    manifesto_url: Link = ""
    social_links: dict[Annotated[str, Field(max_length=40)], Link] = Field(default_factory=dict)
