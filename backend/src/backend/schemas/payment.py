"""Payments to mobilizers and agents."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import Field, StringConstraints

from backend.models.enums import PaymentStatus, UserRole
from backend.schemas.common import ORMModel, WriteModel


class PaymentRead(ORMModel):
    id: uuid.UUID
    campaign: uuid.UUID = Field(validation_alias="campaign_id")
    event: uuid.UUID | None = Field(default=None, validation_alias="event_id")
    event_title: str
    mobilizer: uuid.UUID | None = Field(default=None, validation_alias="mobilizer_id")
    agent: uuid.UUID | None = Field(default=None, validation_alias="agent_id")
    assignment: uuid.UUID | None = Field(default=None, validation_alias="assignment_id")
    scheduled_by: uuid.UUID | None = Field(default=None, validation_alias="scheduled_by_id")
    # Who approves it; None for a payment from before routing, which the manager approves.
    approver_role: UserRole | None
    recipient_name: str
    recipient_phone: str
    amount_kes: int
    status: PaymentStatus
    reference: str
    provider: str
    failure_reason: str
    stuck: bool
    paid_at: datetime | None
    created_at: datetime


class PaymentCreate(WriteModel):
    """A payment for a done assignment, to its mobilizer or agent, for its amount."""

    assignment: uuid.UUID


class PaymentDecline(WriteModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]


class PaymentPaid(WriteModel):
    reference: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


class PayoutMode(ORMModel):
    mode: str
    moves_money: bool
