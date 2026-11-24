"""Online meetings and call alerts."""

import uuid
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator

from backend.schemas.common import ORMModel, WriteModel

# The browsers' push services; the server posts alerts to these hosts only.
PUSH_HOSTS = (
    "fcm.googleapis.com",
    "updates.push.services.mozilla.com",
    "push.services.mozilla.com",
    ".push.apple.com",
    ".notify.windows.com",
)


def push_endpoint(value: str) -> str:
    """An https address on a known push service."""
    # Characters that let URL parsers disagree about the host are refused outright.
    if any(c in value for c in "\\@") or any(c.isspace() for c in value):
        raise ValueError("That is not a browser push address.")
    parts = urlsplit(value)
    host = (parts.hostname or "").lower()
    known = any(host == h or (h.startswith(".") and host.endswith(h)) for h in PUSH_HOSTS)
    if parts.scheme != "https" or not known or parts.port not in (None, 443):
        raise ValueError("That is not a browser push address.")
    return value


class MeetingStart(WriteModel):
    title: str = Field(min_length=1, max_length=150)
    mode: Literal["audio", "video"] = "video"
    # Both blank rings the whole campaign; a centre rings that centre's team.
    ward: uuid.UUID | None = None
    centre: uuid.UUID | None = None


class MeetingRead(ORMModel):
    id: uuid.UUID
    title: str
    mode: str
    status: str
    ward: uuid.UUID | None = Field(default=None, validation_alias="ward_id")
    centre: uuid.UUID | None = Field(default=None, validation_alias="registration_centre_id")
    started_at: datetime
    ended_at: datetime | None


class MeetingStarted(ORMModel):
    meeting: MeetingRead
    join_path: str
    # How many devices showed the alert.
    alerted: int


class MeetingJoin(ORMModel):
    meeting: MeetingRead
    token: str
    url: str
    can_end: bool


class Stay(ORMModel):
    name: str
    joined_at: datetime
    left_at: datetime | None


class CallRead(ORMModel):
    meeting: MeetingRead
    host: str
    # Who the call was for: "Whole campaign", "Mwiki ward" or "Mwiki Primary centre".
    unit: str
    minutes: int
    attendance: list[Stay]


class PushKey(ORMModel):
    key: str


class PushKeys(WriteModel):
    p256dh: str = Field(min_length=1, max_length=200)
    auth: str = Field(min_length=1, max_length=100)


class PushSubscribe(WriteModel):
    endpoint: str = Field(min_length=10, max_length=2000)
    keys: PushKeys

    _known = field_validator("endpoint")(push_endpoint)


class PushUnsubscribe(WriteModel):
    endpoint: str = Field(min_length=10, max_length=2000)
