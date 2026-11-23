"""The website's posts and homepage items, as the public site reads them and the editors write
them."""

import math
import re
import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import AfterValidator, Field, computed_field, field_validator, model_validator

from backend.models import PostKind, PostLabel
from backend.schemas.common import Named, ORMModel, WriteModel, partial, plain_text, trimmed
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


def _target(value: str) -> str:
    value = plain_text(value).strip()
    if value and not (
        (value.startswith("/") and not value.startswith("//")) or value.startswith("https://")
    ):
        raise ValueError("Use a page on this site such as /volunteer, or an https:// address.")
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
    image_url: str


class IssueAdminRead(AdminFields, IssueRead):
    pass


class IssueCreate(WriteModel):
    title: Line
    summary: trimmed(300) = ""
    what_we_will_do: Body = ""
    why_it_matters: Body = ""
    image_url: Image = ""
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
