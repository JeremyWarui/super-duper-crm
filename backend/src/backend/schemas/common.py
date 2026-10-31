"""Base classes shared by the request and response schemas."""

import unicodedata
import uuid

from pydantic import BaseModel, ConfigDict, Field

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


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, extra="forbid")


class WriteModel(BaseModel):
    """A request body; an unknown field is an error."""

    model_config = ConfigDict(extra="forbid")


class LoginDetails(WriteModel):
    """Who a new login is for."""

    username: str = Field(min_length=3, max_length=150, pattern=r"^[A-Za-z0-9._-]+$")
    first_name: str = Field(default="", max_length=150)
    last_name: str = Field(default="", max_length=150)
    phone: str = Field(default="", max_length=20)
    email: str = Field(default="", max_length=254)


class NewLogin(ORMModel):
    """A login just created; `password` is shown this once."""

    id: uuid.UUID
    username: str
    full_name: str
    password: str
