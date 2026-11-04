"""Moving a payment through scheduled, sending, paid, failed and cancelled, for any payment table.

Every move is one conditional UPDATE, so two requests cannot both move the same payment, and a
provider's answer lands only on the attempt it belongs to.
"""

import asyncio
import logging
import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import PartyPayment, Payment, PaymentStatus
from backend.models.payment import OUTCOME_UNKNOWN, PayoutMixin
from backend.services.errors import Refused
from backend.services.payouts import PayoutProvider

logger = logging.getLogger(__name__)

# A payment still waiting to go out: freshly scheduled, or a send that failed.
OPEN = (PaymentStatus.SCHEDULED, PaymentStatus.FAILED)
# What a provider may report; anything else counts as an unknown outcome.
SETTLED = (PaymentStatus.PAID, PaymentStatus.SENDING, PaymentStatus.FAILED)
SEND_TIMEOUT = 30  # seconds a provider has to answer

# The attempt reference each table sends, so a webhook finds its row: `pay-<id>-<attempt>`.
PREFIX: dict[type, str] = {Payment: "pay", PartyPayment: "party"}
ATTEMPT = re.compile(r"^(pay|party)-([0-9a-f-]{36})-(\d+)$")


def _already(row: PayoutMixin) -> Refused:
    return Refused(f"That payment is already {row.status.label.lower()}.")


async def move(
    session: AsyncSession,
    row: PayoutMixin,
    to: PaymentStatus,
    from_: tuple[PaymentStatus, ...] = OPEN,
    **values: object,
) -> PayoutMixin:
    model = type(row)
    moved = await session.scalar(
        update(model)
        .where(model.id == row.id, model.status.in_(from_))
        .values(status=to, **values)
        .returning(model.id)
    )
    if moved is None:
        await session.refresh(row)
        raise _already(row)
    await session.commit()
    await session.refresh(row)
    return row


async def finish(
    session: AsyncSession,
    row: PayoutMixin,
    attempt: int,
    from_: tuple[PaymentStatus, ...] = (PaymentStatus.SENDING,),
    **values: object,
) -> PayoutMixin:
    """Record an attempt's outcome, unless a person or a later attempt has settled it since."""
    model = type(row)
    landed = await session.execute(
        update(model)
        .where(model.id == row.id, model.status.in_(from_), model.attempts == attempt)
        .values(**values)
    )
    if landed.rowcount == 0 and "status" in values:
        # The one trace of a payment that may have gone out twice.
        logger.error(
            "payout answer for %s %s attempt %d dropped: %s %s",
            model.__tablename__,
            row.id,
            attempt,
            values["status"],
            values.get("reference", ""),
        )
    await session.commit()
    await session.refresh(row)
    return row


async def release(
    session: AsyncSession, row: PayoutMixin, provider: PayoutProvider, phone: str
) -> PayoutMixin:
    """Send an open payment to `phone`, already checked by the caller as the number to pay."""
    if row.status not in OPEN:
        raise _already(row)
    model = type(row)
    attempt = await session.scalar(
        update(model)
        .where(model.id == row.id, model.status.in_(OPEN))
        .values(
            status=PaymentStatus.SENDING,
            attempts=model.attempts + 1,
            sending_since=datetime.now(UTC),
            provider=provider.name,
            recipient_phone=phone,
            failure_reason="",
        )
        .returning(model.attempts)
    )
    if attempt is None:
        await session.refresh(row)
        raise _already(row)
    await session.commit()
    await session.refresh(row)
    try:
        result = await asyncio.wait_for(
            provider.send(
                payment_id=row.id,
                reference=f"{PREFIX[model]}-{row.id}-{attempt}",
                phone=phone,
                name=row.recipient_name,
                amount_kes=row.amount_kes,
            ),
            SEND_TIMEOUT,
        )
        outcome = PaymentStatus(result.status)
    except Exception:  # noqa: BLE001 - the money may have gone; a person settles it
        return await finish(session, row, attempt, failure_reason=OUTCOME_UNKNOWN)
    if outcome not in SETTLED:
        return await finish(session, row, attempt, failure_reason=OUTCOME_UNKNOWN)
    done: dict[str, object] = {
        "status": outcome,
        "reference": (result.reference or "")[:50],
        "failure_reason": "",
    }
    if outcome is PaymentStatus.PAID:
        done["paid_at"] = datetime.now(UTC)
    if outcome is PaymentStatus.FAILED:
        done["failure_reason"] = (result.detail or "")[:200] or "The payout provider refused it."
    return await finish(session, row, attempt, **done)


def require_settleable(row: PayoutMixin) -> None:
    """A payment still waiting on its provider is not settled by hand."""
    if row.status is PaymentStatus.SENDING and not row.stuck:
        raise Refused("That payment is still sending; wait for the payout provider to answer.")


async def mark_not_sent(session: AsyncSession, row: PayoutMixin) -> PayoutMixin:
    """After checking the provider: a payment stuck in sending did not go out, so it can retry."""
    if row.status is not PaymentStatus.SENDING:
        raise Refused("Only a payment stuck in sending can be marked not sent.")
    require_settleable(row)
    return await move(
        session,
        row,
        PaymentStatus.FAILED,
        (PaymentStatus.SENDING,),
        failure_reason="Marked not sent after checking the provider.",
    )


async def mark_paid(session: AsyncSession, row: PayoutMixin, reference: str) -> PayoutMixin:
    """Record by hand that the money went out, under its M-Pesa or bank reference."""
    require_settleable(row)
    return await move(
        session,
        row,
        PaymentStatus.PAID,
        (*OPEN, PaymentStatus.SENDING),
        reference=reference,
        paid_at=datetime.now(UTC),
        provider="",
        failure_reason="",
    )


async def cancel(session: AsyncSession, row: PayoutMixin) -> PayoutMixin:
    return await move(session, row, PaymentStatus.CANCELLED)


async def apply_transfer_event(session: AsyncSession, event: str, data: dict) -> bool:
    """Land a Paystack transfer webhook on the attempt its reference names; False if none."""
    found = ATTEMPT.match(str(data.get("reference") or ""))
    if found is None:
        return False
    model = next(m for m, prefix in PREFIX.items() if prefix == found[1])
    row = await session.get(model, uuid.UUID(found[2]))
    if row is None or row.provider != "paystack":
        return False
    attempt = int(found[3])
    code = str(data.get("transfer_code") or "")[:50]
    if event == "transfer.success":
        await finish(
            session,
            row,
            attempt,
            status=PaymentStatus.PAID,
            reference=code,
            paid_at=datetime.now(UTC),
            failure_reason="",
        )
    elif event in ("transfer.failed", "transfer.reversed"):
        reversed_ = event == "transfer.reversed"
        word = "reversed" if reversed_ else "failed"
        # A reversal can follow a success: the money came back, so it is owed again.
        await finish(
            session,
            row,
            attempt,
            (PaymentStatus.SENDING, PaymentStatus.PAID) if reversed_ else (PaymentStatus.SENDING,),
            status=PaymentStatus.FAILED,
            reference=code,
            paid_at=None,
            failure_reason=f"Paystack says the transfer {word}.",
        )
    else:
        return False
    return True
