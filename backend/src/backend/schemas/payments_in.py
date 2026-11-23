"""M-Pesa contributions: what the payment dialog offers, what it sends, and what it reads back."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from backend.models.enums import PayInMethod, PayInStatus
from backend.schemas.common import WriteModel
from backend.schemas.site import Email


class PayOptions(BaseModel):
    """`prompt` sends an M-Pesa prompt to the phone (a practice one when `practice`); a Paybill or
    Till takes a payment the payer makes themselves and reports by code."""

    prompt: bool
    practice: bool
    paybill: str
    account: str
    till: str
    instructions: str


class PayContribution(WriteModel):
    """`mpesa_code` is needed for the manual method only."""

    method: PayInMethod
    phone: str = Field(min_length=9, max_length=20)
    mpesa_code: str = Field(default="", max_length=20)
    amount_kes: int
    name: str = Field(min_length=2, max_length=150)
    email: Email = ""


class PaymentInRead(BaseModel):
    """`reference` reads the payment's status back while the dialog waits."""

    reference: str
    method: PayInMethod
    status: PayInStatus
    amount_kes: int
    reason: str
    practice: bool = False


class PaymentInRow(PaymentInRead):
    """One contribution on the campaign's list."""

    id: uuid.UUID
    payer_name: str
    payer_phone: str
    mpesa_code: str
    created_at: datetime
    paid_at: datetime | None


class PayReject(WriteModel):
    reason: str = Field(min_length=1, max_length=300)
