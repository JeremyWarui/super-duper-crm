"""The workspace's texts to supporters: drafts, previews and the delivery log."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from backend.schemas.common import ORMModel, WriteModel

# Six parts with the opt-out line added.
BODY_MAX = 895


class MessageDraft(WriteModel):
    campaign: uuid.UUID
    body: str = Field(min_length=1, max_length=BODY_MAX)
    # Blank is every ward the drafter reaches.
    wards: list[uuid.UUID] = Field(default_factory=list, max_length=200)
    # Send at once; only for those who may send.
    send: bool = False


class MessageDecline(WriteModel):
    note: str = Field(default="", max_length=500)


class Reach(ORMModel):
    """Who a message would reach now."""

    recipients: int
    opted_out: int
    no_number: int
    text: str
    parts: int


class AddressableWard(ORMModel):
    id: uuid.UUID
    name: str
    supporters: int


class DeliveryCounts(ORMModel):
    practice: int = 0
    sent: int = 0
    delivered: int = 0
    failed: int = 0


class SmsDraftRead(BaseModel):
    """What a campaign or party text shows in its list: who wrote it, who decided, how it went."""

    id: uuid.UUID
    body: str
    drafted_by: str
    decided_by: str
    created_at: datetime
    decided_at: datetime | None
    note: str
    recipients: int
    delivery: DeliveryCounts
    mine: bool


class MessageRead(SmsDraftRead):
    model_config = ORMModel.model_config

    wards: list[str]
    ward_names: list[str]
    status: Literal["draft", "sent", "declined"]


class MessagesPage(ORMModel):
    sender_id: str
    provider: str
    can_send: bool
    wards: list[AddressableWard]
    messages: list[MessageRead]


class LogRow(ORMModel):
    phone: str
    status: str
    detail: str
    created_at: datetime
    updated_at: datetime | None
