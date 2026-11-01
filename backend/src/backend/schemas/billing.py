"""Plans, subscriptions and their ledger, as the finance officer reads and writes them."""

import re
import unicodedata
import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.models import AccessState, EntryKind, ReceiptMethod, Seat, SubscriptionHold
from backend.schemas.common import ORMModel, WriteModel, plain_text

MAX_KES = 10_000_000
REFERENCE = re.compile(r"[A-Z0-9/-]{1,40}")


def normal_reference(value: str) -> str:
    """One spelling per reference: compatibility forms folded, spaces removed, upper case."""
    folded = unicodedata.normalize("NFKC", value)
    return "".join(folded.split()).upper()


class PlanRead(ORMModel):
    id: uuid.UUID
    name: str
    price_kes: int
    duration_days: int
    description: str
    active: bool
    created_at: datetime


class PlanCreate(WriteModel):
    name: str = Field(min_length=1, max_length=80)
    price_kes: int = Field(ge=0, le=MAX_KES)
    duration_days: int = Field(ge=1, le=730)
    description: str = Field(default="", max_length=2000)
    active: bool = True

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = plain_text(value).strip()
        if not value:
            raise ValueError("Give the plan a name.")
        return value

    @field_validator("description")
    @classmethod
    def _description(cls, value: str) -> str:
        return plain_text(value, lines=True)


class PlanUpdate(WriteModel):
    """Only the fields sent change."""

    name: str | None = Field(default=None, min_length=1, max_length=80)
    price_kes: int | None = Field(default=None, ge=0, le=MAX_KES)
    duration_days: int | None = Field(default=None, ge=1, le=730)
    description: str | None = Field(default=None, max_length=2000)
    active: bool | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = plain_text(value).strip()
        if not value:
            raise ValueError("Give the plan a name.")
        return value

    @field_validator("description")
    @classmethod
    def _description(cls, value: str | None) -> str | None:
        return plain_text(value, lines=True)


class PlanName(BaseModel):
    id: uuid.UUID
    name: str


class SubscriptionRow(BaseModel):
    """One campaign's billing line; `campaign_id` is None once the campaign is deleted."""

    id: uuid.UUID
    campaign_id: uuid.UUID | None
    title: str
    seat: Seat | None
    area_name: str
    candidate_name: str
    plan: PlanName | None
    paid_until: date | None
    state: AccessState
    hold: SubscriptionHold


class SubscriptionPage(BaseModel):
    total: int
    items: list[SubscriptionRow]


class EntryRead(BaseModel):
    id: uuid.UUID
    kind: EntryKind
    plan_name: str | None
    amount_kes: int | None
    method: ReceiptMethod | None
    reference: str | None
    received_on: date
    days: int
    paid_until_before: date | None
    paid_until_after: date
    note: str
    recorded_by: str | None
    created_at: datetime
    voided_at: datetime | None
    void_reason: str | None
    # Only the latest live entry can be voided.
    can_void: bool


class SubscriptionDetail(SubscriptionRow):
    hold_reason: str | None
    read_only_from: date | None
    locks_on: date | None
    entries: list[EntryRead]


class PlanChoice(WriteModel):
    plan: uuid.UUID


def _note(value: str) -> str:
    return plain_text(value, lines=True).strip()


class PaymentCreate(WriteModel):
    amount_kes: int = Field(gt=0, le=MAX_KES)
    method: ReceiptMethod
    reference: str = Field(min_length=1, max_length=80)
    received_on: date
    note: str = Field(default="", max_length=1000)

    @field_validator("reference")
    @classmethod
    def _reference(cls, value: str) -> str:
        value = normal_reference(plain_text(value))
        if not REFERENCE.fullmatch(value):
            raise ValueError("A reference is up to 40 letters, digits, '-' or '/'.")
        return value

    @field_validator("note")
    @classmethod
    def _plain(cls, value: str) -> str:
        return _note(value)


class ExtensionCreate(WriteModel):
    days: int = Field(ge=1, le=365)
    note: str = Field(min_length=1, max_length=1000)

    @field_validator("note")
    @classmethod
    def _plain(cls, value: str) -> str:
        value = _note(value)
        if not value:
            raise ValueError("Say why the access is extended.")
        return value


class VoidCreate(WriteModel):
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def _plain(cls, value: str) -> str:
        value = _note(value)
        if not value:
            raise ValueError("Say why the entry is voided.")
        return value


class HoldChange(WriteModel):
    hold: SubscriptionHold
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("reason")
    @classmethod
    def _plain(cls, value: str | None) -> str | None:
        return None if value is None else (_note(value) or None)

    @model_validator(mode="after")
    def _reason_with_a_hold(self) -> "HoldChange":
        if self.hold is SubscriptionHold.NONE:
            self.reason = None
        elif not self.reason:
            raise ValueError("Say why access is stopped.")
        return self


class FinanceSettings(ORMModel):
    grace_days: int
    read_only_days: int
    payment_instructions: str


class FinanceSettingsUpdate(WriteModel):
    grace_days: int = Field(ge=0, le=60)
    read_only_days: int = Field(ge=0, le=60)
    payment_instructions: str = Field(default="", max_length=2000)

    @field_validator("payment_instructions")
    @classmethod
    def _plain(cls, value: str) -> str:
        return plain_text(value, lines=True)
