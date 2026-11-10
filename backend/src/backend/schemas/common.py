"""Base classes shared by the request and response schemas."""

import unicodedata
import uuid
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    model_validator,
)

# Control, invisible formatting (zero-width, direction overrides), surrogate, private, unassigned,
# and line or paragraph separators.
HIDDEN = frozenset({"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"})
# Characters that draw nothing but count as letters or symbols: Hangul fillers, Braille blank.
BLANK = frozenset("ᅟᅠㅤﾠ⠀")


def plain_text(value: str | None, *, lines: bool = False) -> str | None:
    """Refuse characters a person never types, NUL among them, which Postgres text cannot hold.

    With `lines`, newlines and tabs are allowed.
    """
    if value is None:
        return value
    allowed = "\t\n\r" if lines else ""
    if any(
        (unicodedata.category(ch) in HIDDEN and ch not in allowed) or ch in BLANK for ch in value
    ):
        raise ValueError("Use letters, numbers and punctuation only.")
    return value


# Text a person typed, refused when it holds characters a person never types.
Plain = Annotated[str, AfterValidator(plain_text)]
PlainLines = Annotated[str, AfterValidator(lambda v: plain_text(v, lines=True))]


def trimmed(limit: int):  # type: ignore[no-untyped-def]
    """Plain text of at most `limit` characters, trimmed."""
    return Annotated[str, Field(max_length=limit), AfterValidator(lambda v: plain_text(v).strip())]


def plain_lines(limit: int):  # type: ignore[no-untyped-def]
    """Plain text over several lines, of at most `limit` characters."""
    return Annotated[
        str, Field(max_length=limit), AfterValidator(lambda v: plain_text(v, lines=True))
    ]


STORE_CONSENT = "Consent is required before we can store these details."


def consent(message: str = STORE_CONSENT, *, strict: bool = False):  # type: ignore[no-untyped-def]
    """A consent box that must be ticked; an unticked box is refused with `message`."""

    def ticked(value: bool) -> bool:
        if not value:
            raise ValueError(message)
        return value

    return Annotated[StrictBool if strict else bool, AfterValidator(ticked)]


# A search box's text, refused with a 400 when it holds characters a person never types.
PlainQuery = Annotated[str | None, AfterValidator(plain_text)]

# A campaign title: trimmed, never blank, plain text.
CampaignTitle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=150),
    AfterValidator(plain_text),
]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, extra="forbid")


class Erasable(BaseModel):
    """A row whose personal fields can be erased; an erased row shows no phone."""

    erased_at: datetime | None = None

    @model_validator(mode="after")
    def _no_phone(self):  # type: ignore[no-untyped-def]
        if self.erased_at is not None and hasattr(self, "phone"):
            self.phone = ""
        return self


class WriteModel(BaseModel):
    """A request body; an unknown field is an error."""

    model_config = ConfigDict(extra="forbid")


class LoginDetails(WriteModel):
    """Who a new login is for."""

    username: str = Field(min_length=3, max_length=150, pattern=r"^[A-Za-z0-9._-]+$")
    first_name: Plain = Field(default="", max_length=150)
    last_name: Plain = Field(default="", max_length=150)
    phone: Plain = Field(default="", max_length=20)
    email: Plain = Field(default="", max_length=254)


# How a login's sign-in link went out; "none" when it has no email.
Invite = Literal["email", "none"]


class NewLogin(ORMModel):
    """A login just created, and how its invite link went out."""

    id: uuid.UUID
    username: str
    full_name: str
    invite: Invite

    @classmethod
    def of(cls, login: object, invite: Invite, **extra: object) -> Self:
        """The answer for a login just made: its fields, how its invite went, and `extra`."""
        taken = {
            name: getattr(login, name)
            for name in cls.model_fields
            if name != "invite" and name not in extra
        }
        return cls(**taken, invite=invite, **extra)
