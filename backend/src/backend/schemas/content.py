"""The party's leaders and posts, as the public site reads them and the superuser edits them."""

import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import AfterValidator, Field, field_validator, model_validator

from backend.models import PostKind
from backend.schemas.common import ORMModel, WriteModel, plain_text


def _image(value: str) -> str:
    value = plain_text(value).strip()
    if value and (not value.startswith("https://") or any(c.isspace() for c in value)):
        raise ValueError("Use an image address starting with https://.")
    return value


def _line(value: str) -> str:
    value = plain_text(value).strip()
    if not value:
        raise ValueError("This cannot be empty.")
    return value


def _text(value: str) -> str:
    return plain_text(value, lines=True)


Image = Annotated[str, Field(max_length=500), AfterValidator(_image)]
Line = Annotated[str, Field(min_length=1, max_length=150), AfterValidator(_line)]
Venue = Annotated[str, Field(max_length=150), AfterValidator(lambda v: plain_text(v).strip())]
Body = Annotated[str, Field(max_length=20_000), AfterValidator(_text)]


class LeaderRead(ORMModel):
    id: uuid.UUID
    name: str
    position: str
    bio: str
    photo_url: str


class LeaderAdminRead(LeaderRead):
    sort_order: int
    published: bool
    updated_at: datetime


class LeaderCreate(WriteModel):
    name: Line
    position: Line
    bio: Body = ""
    photo_url: Image = ""
    sort_order: int = Field(default=0, ge=0, le=10_000)
    published: bool = False


class LeaderUpdate(WriteModel):
    """Only the fields sent change."""

    name: Line | None = None
    position: Line | None = None
    bio: Body | None = None
    photo_url: Image | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    published: bool | None = None


class PostRead(ORMModel):
    id: uuid.UUID
    kind: PostKind
    title: str
    body: str
    image_url: str
    event_date: date | None
    venue: str
    published_on: date | None


class PostAdminRead(PostRead):
    published: bool
    updated_at: datetime


class PostCreate(WriteModel):
    kind: PostKind
    title: Line
    body: Body = ""
    image_url: Image = ""
    event_date: date | None = None
    venue: Venue = ""
    published: bool = False

    @model_validator(mode="after")
    def _event_fields(self) -> "PostCreate":
        if self.kind is PostKind.EVENT and self.event_date is None:
            raise ValueError("An event needs a date.")
        if self.kind is PostKind.NEWS and (self.event_date is not None or self.venue):
            raise ValueError("A news post has no date or venue.")
        return self


class PostUpdate(WriteModel):
    """Only the fields sent change; a post keeps its kind."""

    title: Line | None = None
    body: Body | None = None
    image_url: Image | None = None
    event_date: date | None = None
    venue: Venue | None = None
    published: bool | None = None

    @field_validator("event_date")
    @classmethod
    def _date(cls, value: date | None) -> date | None:
        if value is None:
            raise ValueError("An event needs a date.")
        return value


class BranchCounty(ORMModel):
    id: uuid.UUID
    name: str


class BranchRead(ORMModel):
    """A published branch as the public site shows it."""

    county: BranchCounty
    chairperson: str
    secretary: str
    office_address: str
    phone: str
    email: str
    next_meeting_on: date | None
    next_meeting_venue: str


class BranchWard(ORMModel):
    id: uuid.UUID
    name: str


class BranchConstituency(ORMModel):
    id: uuid.UUID
    name: str
    wards: list[BranchWard]


class BranchDetail(BranchRead):
    """One branch, with the county's constituencies and their wards as its sub-branches."""

    constituencies: list[BranchConstituency]


class BranchAdminRead(BranchRead):
    published: bool
    updated_at: datetime


class CountyBranch(ORMModel):
    """A county and its branch, or None before the superuser writes one."""

    county: BranchCounty
    branch: BranchAdminRead | None


class BranchUpdate(WriteModel):
    """The whole branch; the request replaces every field."""

    chairperson: Venue = ""
    secretary: Venue = ""
    office_address: Annotated[
        str, Field(max_length=300), AfterValidator(lambda v: plain_text(v).strip())
    ] = ""
    phone: Annotated[str, Field(max_length=20), AfterValidator(lambda v: plain_text(v).strip())] = (
        ""
    )
    email: Annotated[
        str, Field(max_length=254), AfterValidator(lambda v: plain_text(v).strip())
    ] = ""
    next_meeting_on: date | None = None
    next_meeting_venue: Venue = ""
    published: bool = False

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        if value and ("@" not in value or any(c.isspace() for c in value)):
            raise ValueError("Use an email address like name@example.com.")
        return value
