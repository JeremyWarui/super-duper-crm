"""The party's leaders and posts, as the public site reads them and the superuser edits them."""

import math
import re
import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import AfterValidator, Field, computed_field, field_validator, model_validator

from backend.models import BranchOffice, PostKind, PostLabel, Seat, TermEnd, TermStart
from backend.schemas.common import Named, ORMModel, WriteModel, partial, plain_text, trimmed
from backend.schemas.site import email_address
from backend.services import rich_text

UPLOADED = re.compile(r"^/api/files/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/$")


def _address(refusal: str, *, uploaded: bool):  # type: ignore[no-untyped-def]
    """An https:// address, refused with `refusal`; with `uploaded`, a file uploaded here too."""

    def check(value: str) -> str:
        value = plain_text(value).strip()
        if uploaded and UPLOADED.match(value):
            return value
        if value and (not value.startswith("https://") or any(c.isspace() for c in value)):
            raise ValueError(refusal)
        return value

    return check


def _line(value: str) -> str:
    value = plain_text(value).strip()
    if not value:
        raise ValueError("This cannot be empty.")
    return value


def _text(value: str) -> str:
    return plain_text(value, lines=True)


Image = Annotated[
    str,
    Field(max_length=500),
    AfterValidator(
        _address("Upload an image, or use an address starting with https://.", uploaded=True)
    ),
]
Line = Annotated[str, Field(min_length=1, max_length=150), AfterValidator(_line)]
Link = Annotated[
    str,
    Field(max_length=500),
    AfterValidator(_address("Use an address starting with https://.", uploaded=False)),
]
RequiredLink = Annotated[
    str,
    Field(min_length=1, max_length=500),
    AfterValidator(_address("Use an address starting with https://.", uploaded=False)),
]
Pdf = Annotated[
    str,
    Field(max_length=500),
    AfterValidator(
        _address("Upload a PDF, or use an address starting with https://.", uploaded=True)
    ),
]
Place = trimmed(80)
Reference = trimmed(40)
Venue = trimmed(150)
Body = Annotated[str, Field(max_length=20_000), AfterValidator(_text)]
# Text from the rich text editor as HTML, cleaned to the tags `rich_text` keeps.
RichBody = Annotated[
    str, Field(max_length=50_000), AfterValidator(lambda v: rich_text.clean(_text(v)))
]
Order = Annotated[int, Field(ge=0, le=10_000)]


class AdminFields(ORMModel):
    """What the editor shows beside an ordered content row: its place, whether it is live, when
    it last changed."""

    sort_order: int
    published: bool
    updated_at: datetime


class LeaderRead(ORMModel):
    id: uuid.UUID
    name: str
    position: str
    bio: str
    photo_url: str


class LeaderAdminRead(AdminFields, LeaderRead):
    pass


class LeaderCreate(WriteModel):
    name: Line
    position: Line
    bio: RichBody = ""
    photo_url: Image = ""
    sort_order: Order = 0
    published: bool = False


LeaderUpdate = partial(LeaderCreate, "LeaderUpdate")


PostCounty = Named


EXCERPT = 300


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
        return max(1, math.ceil(len(rich_text.text(self.body).split()) / 200))

    @computed_field
    @property
    def excerpt(self) -> str:
        """The body's opening words as plain text, for cards and lists."""
        words = rich_text.text(self.body).replace("\n", " ")
        return words if len(words) <= EXCERPT else words[: EXCERPT - 1].rsplit(" ", 1)[0] + "…"


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
    body: RichBody = ""
    image_url: Image = ""
    event_date: date | None = None
    venue: Venue = ""
    label: PostLabel = PostLabel.NEWS
    place: Place = ""
    author: Venue = ""
    author_photo_url: Image = ""
    reference: Reference = ""
    pdf_url: Pdf = ""
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
    body: RichBody | None = None
    image_url: Image | None = None
    event_date: date | None = None
    venue: Venue | None = None
    label: PostLabel | None = None
    place: Place | None = None
    author: Venue | None = None
    author_photo_url: Image | None = None
    reference: Reference | None = None
    pdf_url: Pdf | None = None
    county_id: uuid.UUID | None = Field(default=None, description="Send null to clear it.")
    published: bool | None = None

    @field_validator("event_date")
    @classmethod
    def _date(cls, value: date | None) -> date | None:
        if value is None:
            raise ValueError("An event needs a date.")
        return value


BranchCounty = Named


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


BranchWard = Named


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

    office_address: trimmed(300) = ""
    phone: trimmed(20) = ""
    email: Annotated[trimmed(254), AfterValidator(email_address)] = ""
    next_meeting_on: date | None = None
    next_meeting_venue: Venue = ""
    published: bool = False


def _target(value: str) -> str:
    value = plain_text(value).strip()
    if value and not (
        (value.startswith("/") and not value.startswith("//")) or value.startswith("https://")
    ):
        raise ValueError("Use a page on this site such as /join-party, or an https:// address.")
    if any(c.isspace() for c in value):
        raise ValueError("A link has no spaces.")
    return value


Target = Annotated[str, Field(max_length=500), AfterValidator(_target)]


class SlideRead(ORMModel):
    id: uuid.UUID
    image_url: str
    kicker: str
    headline: str
    line: str
    button_label: str
    button_url: str


class SlideAdminRead(AdminFields, SlideRead):
    pass


class SlideCreate(WriteModel):
    image_url: Image = ""
    kicker: trimmed(80) = ""
    headline: Annotated[str, Field(min_length=1, max_length=120), AfterValidator(_line)]
    line: trimmed(300) = ""
    button_label: trimmed(40) = ""
    button_url: Target = ""
    sort_order: Order = 0
    published: bool = False


SlideUpdate = partial(SlideCreate, "SlideUpdate")


class IssueRead(ORMModel):
    id: uuid.UUID
    title: str
    summary: str
    what_we_will_do: str
    why_it_matters: str


class IssueAdminRead(AdminFields, IssueRead):
    pass


class IssueCreate(WriteModel):
    title: Line
    summary: trimmed(300) = ""
    what_we_will_do: Body = ""
    why_it_matters: Body = ""
    sort_order: Order = 0
    published: bool = False


IssueUpdate = partial(IssueCreate, "IssueUpdate")


class DocumentRead(ORMModel):
    id: uuid.UUID
    title: str
    url: str


class DocumentAdminRead(AdminFields, DocumentRead):
    pass


class DocumentCreate(WriteModel):
    title: Line
    url: RequiredLink
    sort_order: Order = 0
    published: bool = False


DocumentUpdate = partial(DocumentCreate, "DocumentUpdate")


class AboutItemRead(ORMModel):
    """A value or a party organ on the About page."""

    id: uuid.UUID
    title: str
    text: str


class AboutItemAdminRead(AdminFields, AboutItemRead):
    pass


class AboutItemCreate(WriteModel):
    title: Line
    text: trimmed(300) = ""
    sort_order: Order = 0
    published: bool = False


AboutItemUpdate = partial(AboutItemCreate, "AboutItemUpdate")


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


ResultUpdate = partial(
    ResultCreate,
    "ResultUpdate",
    "Only the fields sent change; a null declared_on marks the race as still counting.",
)


Duration = Annotated[str, Field(max_length=8, pattern=r"^(\d{1,2}:)?\d{1,2}:\d{2}$|^$")]


class VideoRead(ORMModel):
    id: uuid.UUID
    title: str
    url: str
    thumbnail_url: str
    duration: str


class VideoAdminRead(AdminFields, VideoRead):
    pass


class VideoCreate(WriteModel):
    title: Line
    url: RequiredLink
    thumbnail_url: Image = ""
    duration: Duration = ""
    sort_order: Order = 0
    published: bool = False


VideoUpdate = partial(VideoCreate, "VideoUpdate")


class OfficialAppoint(WriteModel):
    """A term for an approved member; `title` names an office of kind "other"."""

    office: BranchOffice
    title: trimmed(80) = ""
    member: uuid.UUID
    term_start: date
    term_end: date | None = None
    start_reason: TermStart = TermStart.ELECTED
    minutes_file: uuid.UUID | None = None
    note: trimmed(1000) = ""

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
