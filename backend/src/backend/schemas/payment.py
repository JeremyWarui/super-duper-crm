"""Payments to mobilizers."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import Field, StrictInt, StringConstraints

from backend.models.enums import PaymentStatus
from backend.schemas.common import ORMModel, WriteModel


class PaymentRead(ORMModel):
    id: uuid.UUID
    campaign: uuid.UUID = Field(validation_alias="campaign_id")
    event: uuid.UUID | None = Field(default=None, validation_alias="event_id")
    event_title: str
    mobilizer: uuid.UUID | None = Field(default=None, validation_alias="mobilizer_id")
    recipient_name: str
    recipient_phone: str
    amount_kes: int
    status: PaymentStatus
    reference: str
    paid_at: datetime | None
    created_at: datetime


class PaymentCreate(WriteModel):
    """A payment for an event; the mobilizer defaults to the one the event is credited to."""

    campaign: uuid.UUID
    event: uuid.UUID
    mobilizer: uuid.UUID | None = None
    amount_kes: StrictInt = Field(gt=0, le=1_000_000)


class PaymentPaid(WriteModel):
    reference: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
