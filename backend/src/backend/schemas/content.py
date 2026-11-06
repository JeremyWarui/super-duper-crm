"""The party's leaders and posts, as the public site reads them and the superuser edits them."""

import math
import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import AfterValidator, Field, computed_field, field_validator, model_validator

from backend.models import BranchOffice, PostKind, PostLabel, Seat, TermEnd, TermStart
from backend.schemas.common import ORMModel, WriteModel, plain_text


def _image(value: str) -> str:
    value = plain_text(value).strip()
    if value and (not value.startswith("https://") or any(c.isspace() for c in value)):
        raise ValueError("Use an image address starting with https://.")
    return value


def _https(value: str) -> str:
    value = plain_text(value).strip()
    if value and (not value.startswith("https://") or any(c.isspace() for c in value)):
        raise ValueError("Use an address starting with https://.")
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
Link = Annotated[str, Field(max_length=500), AfterValidator(_https)]
Place = Annotated[str, Field(max_length=80), AfterValidator(lambda v: plain_text(v).strip())]
Reference = Annotated[str, Field(max_length=40), AfterValidator(lambda v: plain_text(v).strip())]
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


class PostCounty(ORMModel):
    id: uuid.UUID
    name: str


class _Post(ORMModel):
    id: uuid.UUID
    kind: PostKind
    label: PostLabel
    title: str
    body: str
    image_url: str
    event_date: date | None
    venue: str
    place: str
    author: str
    author_photo_url: str
    reference: str
    pdf_url: str
    published_on: date | None

    @computed_field
    @property
    def read_minutes(self) -> int:
        """Minutes to read the body at 200 words a minute, at least one."""
        return max(1, math.ceil(len(self.body.split()) / 200))


class PostRead(_Post):
    """A published post; an event names its county when it has one."""

    county: PostCounty | None


class PostAdminRead(_Post):
    county_id: uuid.UUID | None
    published: bool
    updated_at: datetime


class PostCreate(WriteModel):
    kind: PostKind
    title: Line
    body: Body = ""
    image_url: Image = ""
    event_date: date | None = None
    venue: Venue = ""
    label: PostLabel = PostLabel.NEWS
    place: Place = ""
    author: Venue = ""
    author_photo_url: Image = ""
    reference: Reference = ""
    pdf_url: Link = ""
    county_id: uuid.UUID | None = None
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
    label: PostLabel | None = None
    place: Place | None = None
    author: Venue | None = None
    author_photo_url: Image | None = None
    reference: Reference | None = None
    pdf_url: Link | None = None
    county_id: uuid.UUID | None = Field(default=None, description="Send null to clear it.")
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


class PublicOfficial(ORMModel):
    """An official in office, as the website names them."""

    office: BranchOffice
    label: str
    name: str


class BranchRead(ORMModel):
    """A published branch as the public site shows it, with its officials in office today."""

    county: BranchCounty
    officials: list[PublicOfficial]
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


def _target(value: str) -> str:
    value = plain_text(value).strip()
    if value and not (
        (value.startswith("/") and not value.startswith("//")) or value.startswith("https://")
    ):
        raise ValueError("Use a page on this site such as /join-party, or an https:// address.")
    if any(c.isspace() for c in value):
        raise ValueError("A link has no spaces.")
    return value


def _short(limit: int):
    return Annotated[str, Field(max_length=limit), AfterValidator(lambda v: plain_text(v).strip())]


Target = Annotated[str, Field(max_length=500), AfterValidator(_target)]
Order = Annotated[int, Field(ge=0, le=10_000)]


class SlideRead(ORMModel):
    id: uuid.UUID
    image_url: str
    kicker: str
    headline: str
    line: str
    button_label: str
    button_url: str


class SlideAdminRead(SlideRead):
    sort_order: int
    published: bool
    updated_at: datetime


class SlideCreate(WriteModel):
    image_url: Image = ""
    kicker: _short(80) = ""
    headline: Annotated[str, Field(min_length=1, max_length=120), AfterValidator(_line)]
    line: _short(300) = ""
    button_label: _short(40) = ""
    button_url: Target = ""
    sort_order: Order = 0
    published: bool = False


class SlideUpdate(WriteModel):
    """Only the fields sent change."""

    image_url: Image | None = None
    kicker: _short(80) | None = None
    headline: Annotated[str, Field(min_length=1, max_length=120), AfterValidator(_line)] | None = (
        None
    )
    line: _short(300) | None = None
    button_label: _short(40) | None = None
    button_url: Target | None = None
    sort_order: Order | None = None
    published: bool | None = None


class IssueRead(ORMModel):
    id: uuid.UUID
    title: str
    summary: str
    what_we_will_do: str
    why_it_matters: str


class IssueAdminRead(IssueRead):
    sort_order: int
    published: bool
    updated_at: datetime


class IssueCreate(WriteModel):
    title: Line
    summary: _short(300) = ""
    what_we_will_do: Body = ""
    why_it_matters: Body = ""
    sort_order: Order = 0
    published: bool = False


class IssueUpdate(WriteModel):
    """Only the fields sent change."""

    title: Line | None = None
    summary: _short(300) | None = None
    what_we_will_do: Body | None = None
    why_it_matters: Body | None = None
    sort_order: Order | None = None
    published: bool | None = None


class DocumentRead(ORMModel):
    id: uuid.UUID
    title: str
    url: str


class DocumentAdminRead(DocumentRead):
    sort_order: int
    published: bool
    updated_at: datetime


class DocumentCreate(WriteModel):
    title: Line
    url: Annotated[str, Field(min_length=1, max_length=500), AfterValidator(_https)]
    sort_order: Order = 0
    published: bool = False


class DocumentUpdate(WriteModel):
    """Only the fields sent change."""

    title: Line | None = None
    url: Annotated[str, Field(min_length=1, max_length=500), AfterValidator(_https)] | None = None
    sort_order: Order | None = None
    published: bool | None = None


class AboutItemRead(ORMModel):
    """A value or a party organ on the About page."""

    id: uuid.UUID
    title: str
    text: str


class AboutItemAdminRead(AboutItemRead):
    sort_order: int
    published: bool
    updated_at: datetime


class AboutItemCreate(WriteModel):
    title: Line
    text: _short(300) = ""
    sort_order: Order = 0
    published: bool = False


class AboutItemUpdate(WriteModel):
    """Only the fields sent change."""

    title: Line | None = None
    text: _short(300) | None = None
    sort_order: Order | None = None
    published: bool | None = None


Votes = Annotated[int, Field(ge=0, le=10_000_000)]


class ResultRead(ORMModel):
    """One candidate's votes in a primary race, a race being one seat in one area."""

    id: uuid.UUID
    seat: Seat
    area: str
    candidate: str
    votes: int
    declared_on: date | None
    demo: bool


class ResultAdminRead(ResultRead):
    published: bool
    updated_at: datetime


class ResultCreate(WriteModel):
    seat: Seat
    area: Line
    candidate: Line
    votes: Votes = 0
    declared_on: date | None = None
    published: bool = False


class ResultUpdate(WriteModel):
    """Only the fields sent change; a null declared_on marks the race as still counting."""

    seat: Seat | None = None
    area: Line | None = None
    candidate: Line | None = None
    votes: Votes | None = None
    declared_on: date | None = None
    published: bool | None = None


Duration = Annotated[str, Field(max_length=8, pattern=r"^(\d{1,2}:)?\d{1,2}:\d{2}$|^$")]


class VideoRead(ORMModel):
    id: uuid.UUID
    title: str
    url: str
    thumbnail_url: str
    duration: str


class VideoAdminRead(VideoRead):
    sort_order: int
    published: bool
    updated_at: datetime


class VideoCreate(WriteModel):
    title: Line
    url: Annotated[str, Field(min_length=1, max_length=500), AfterValidator(_https)]
    thumbnail_url: Image = ""
    duration: Duration = ""
    sort_order: Order = 0
    published: bool = False


class VideoUpdate(WriteModel):
    """Only the fields sent change."""

    title: Line | None = None
    url: Annotated[str, Field(min_length=1, max_length=500), AfterValidator(_https)] | None = None
    thumbnail_url: Image | None = None
    duration: Duration | None = None
    sort_order: Order | None = None
    published: bool | None = None


class OfficialAppoint(WriteModel):
    """A term for an approved member; `title` names an office of kind "other"."""

    office: BranchOffice
    title: Annotated[str, Field(max_length=80), AfterValidator(lambda v: plain_text(v).strip())] = (
        ""
    )
    member: uuid.UUID
    term_start: date
    term_end: date | None = None
    start_reason: TermStart = TermStart.ELECTED
    minutes_file: uuid.UUID | None = None
    note: Annotated[
        str, Field(max_length=1000), AfterValidator(lambda v: plain_text(v).strip())
    ] = ""

    @model_validator(mode="after")
    def _whole(self) -> "OfficialAppoint":
        if self.office is BranchOffice.OTHER and not self.title:
            raise ValueError("Name the office.")
        if self.term_end is not None and self.term_end < self.term_start:
            raise ValueError("A term cannot end before it starts.")
        if self.start_reason is TermStart.RECORDED:
            raise ValueError("A new term is elected or an interim appointment.")
        return self


class OfficialEnd(WriteModel):
    term_end: date
    end_reason: TermEnd

    @field_validator("end_reason")
    @classmethod
    def _not_replaced(cls, value: TermEnd) -> TermEnd:
        if value is TermEnd.REPLACED:
            raise ValueError("Appoint the new holder instead; that ends this term.")
        return value


class OfficialRead(ORMModel):
    id: uuid.UUID
    office: BranchOffice
    label: str
    title: str
    member: uuid.UUID | None = Field(validation_alias="member_id")
    holder_name: str
    term_start: date
    term_end: date | None
    start_reason: TermStart
    end_reason: TermEnd | None
    has_minutes: bool
    note: str
    # The holder is no longer an approved member; the website no longer names them.
    lapsed: bool = False


class OfficialsRead(ORMModel):
    current: list[OfficialRead]
    upcoming: list[OfficialRead]
    history: list[OfficialRead]


class MinutesRead(ORMModel):
    id: uuid.UUID
    name: str
