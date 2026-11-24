"""The workspace's texts to supporters: drafts, previews and the delivery log."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from backend.models.enums import SupportLevel
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
    # Bulk political texts go out in English or Kiswahili only.
    language: Literal["en", "sw"] = "en"
    # Who it goes to by support level; opposed contacts only when picked.
    support_levels: list[SupportLevel] = Field(
        default_factory=lambda: [SupportLevel.SUPPORTER, SupportLevel.UNDECIDED],
        min_length=1,
        max_length=3,
    )


class MessageApprove(WriteModel):
    """The approver confirms the language the text is in."""

    language: Literal["en", "sw"]


class MessageDecline(WriteModel):
    note: str = Field(default="", max_length=500)


class Reach(ORMModel):
    """Who a message would reach now."""

    recipients: int
    opted_out: int
    no_number: int
    text: str
    parts: int
    # Recipients x parts x the price of one part.
    estimated_cost_cents: int


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
    """What a text shows in its list: who wrote it, who decided, how it went."""

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
    support_levels: list[str] = []
    status: Literal["draft", "sent", "declined"]
    language: str = "en"


class MessagesPage(ORMModel):
    sender_id: str
    provider: str
    can_send: bool
    part_price_cents: int
    wards: list[AddressableWard]
    messages: list[MessageRead]


class LogRow(ORMModel):
    phone: str
    status: str
    detail: str
    created_at: datetime
    updated_at: datetime | None


class TestText(WriteModel):
    campaign: uuid.UUID
    phone: str = Field(min_length=3, max_length=20)
    body: str = Field(min_length=1, max_length=BODY_MAX)


class TestTextResult(ORMModel):
    message: str


class SmsRunRead(ORMModel):
    id: uuid.UUID
    message: uuid.UUID = Field(validation_alias="message_id")
    status: str
    language: str
    text: str
    vetting_ref: str
    targeted: int
    excluded_no_consent: int
    excluded_opted_out: int
    sent: int
    failed: int
    delivered: int = 0
    segments: int
    estimated_cost_cents: int
    actual_cost_cents: int
    halt_reason: str
    created_at: datetime
    completed_at: datetime | None
    # When a run waiting for the sending window may start.
    waiting_until: datetime | None = None


class RunHalt(WriteModel):
    reason: str = Field(min_length=1, max_length=500)


class RunVetting(WriteModel):
    reference: str = Field(min_length=1, max_length=100)
