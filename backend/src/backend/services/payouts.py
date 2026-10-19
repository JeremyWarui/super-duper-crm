"""Sending a payment to a mobilizer's phone: practice mode now, a real provider behind it later."""

import uuid
from dataclasses import dataclass
from typing import Protocol

from backend.models import PaymentStatus


@dataclass
class PayoutResult:
    """PAID; SENDING when the provider confirms later; FAILED only if the money did not go.

    A provider that cannot tell raises instead, and the payment stays in SENDING for a person
    to resolve, so an unknown outcome is never retried into a second payment.
    """

    status: PaymentStatus
    reference: str = ""
    detail: str = ""


class PayoutProvider(Protocol):
    name: str
    moves_money: bool

    async def send(
        self, *, payment_id: uuid.UUID, reference: str, phone: str, name: str, amount_kes: int
    ) -> PayoutResult:
        """`reference` is unique to this attempt, so the provider can refuse a repeat of it."""
        ...


class PracticePayouts:
    """Moves no money: every payment is marked paid under a PRACTICE reference."""

    name = "practice"
    moves_money = False

    async def send(
        self, *, payment_id: uuid.UUID, reference: str, phone: str, name: str, amount_kes: int
    ) -> PayoutResult:
        return PayoutResult(PaymentStatus.PAID, f"PRACTICE-{payment_id.hex[:10].upper()}")


def get_payout_provider() -> PayoutProvider:
    return PracticePayouts()
