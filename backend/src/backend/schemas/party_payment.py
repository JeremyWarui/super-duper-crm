"""Payments the party makes: who is paid, for which campaign, and what it adds up to."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, Field, StrictInt, StringConstraints, model_validator

from backend.models.enums import PayeeKind, PaymentStatus
from backend.schemas.common import ORMModel, WriteModel, plain_text

Line = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=150), AfterValidator(plain_text)
]


class PartyPaymentRead(ORMModel):
    id: uuid.UUID
    payee_kind: PayeeKind
    member: uuid.UUID | None = Field(default=None, validation_alias="member_id")
    volunteer: uuid.UUID | None = Field(default=None, validation_alias="volunteer_id")
    recipient_name: str
    recipient_phone: str
    polling_station: str
    aspirant: uuid.UUID | None = Field(default=None, validation_alias="aspirant_id")
    campaign_label: str
    purpose: str
    amount_kes: int
    status: PaymentStatus
    reference: str
    provider: str
    failure_reason: str
    stuck: bool
    paid_at: datetime | None
    created_at: datetime


class PartyPaymentCreate(WriteModel):
    """A payee picked from the member or volunteer register, or a name and phone typed in."""

    payee_kind: PayeeKind
    member: uuid.UUID | None = None
    volunteer: uuid.UUID | None = None
    name: Line = ""
    phone: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)] = ""
    centre: uuid.UUID | None = None
    aspirant: uuid.UUID | None = None
    purpose: Line = ""
    amount_kes: StrictInt = Field(gt=0, le=1_000_000)

    @model_validator(mode="after")
    def _one_payee(self) -> "PartyPaymentCreate":
        if self.member and self.volunteer:
            raise ValueError("Pick a member or a volunteer, not both.")
        if not (self.member or self.volunteer) and not (self.name and self.phone):
            raise ValueError("Give the payee's name and phone, or pick them from a register.")
        return self


class PayeeOption(ORMModel):
    """A register row the finance officer can pay."""

    source: Literal["member", "volunteer"]
    id: uuid.UUID
    name: str
    phone: str
    polling_station: str


class CampaignOption(ORMModel):
    aspirant: uuid.UUID
    label: str


class SpendRow(ORMModel):
    """One campaign's spend; `aspirant` NULL with a blank label is party work."""

    aspirant: uuid.UUID | None
    label: str
    paid_kes: int
    owed_kes: int
    payments: int


class SpendReport(ORMModel):
    rows: list[SpendRow]
    paid_kes: int
    owed_kes: int
