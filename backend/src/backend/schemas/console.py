"""The party console's top bar: search hits and notification counts."""

import uuid
from typing import Literal

from backend.schemas.common import ORMModel


class SearchHit(ORMModel):
    kind: Literal["member", "aspirant"]
    id: uuid.UUID
    label: str
    detail: str


class Notification(ORMModel):
    """`key` names what waits; the console words it and links it to its page."""

    key: Literal["pending_members", "submitted_aspirants", "held_payments", "payments_to_approve"]
    count: int
