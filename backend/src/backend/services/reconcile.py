"""Comparing the payments ledger with the payout provider's own record of its transfers.

A run lists every disagreement and changes no payment: a person settles each one.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Payment, PaymentStatus, ReconcileDifference, ReconcileRun
from backend.services.clock import as_utc
from backend.services.payout_flow import ATTEMPT
from backend.services.payouts import PAYSTACK_DEAD, PayoutProvider, Transfer, get_payout_provider

logger = logging.getLogger(__name__)

# How far back each run looks.
WINDOW = timedelta(days=30)
# How long a send may wait on its webhook before a difference in state is listed.
GRACE = timedelta(hours=24)


def provider_state(transfer: Transfer) -> PaymentStatus:
    if transfer.status == "success":
        return PaymentStatus.PAID
    if transfer.status in PAYSTACK_DEAD:
        return PaymentStatus.FAILED
    return PaymentStatus.SENDING


def _compare(row: Payment, transfer: Transfer, now: datetime) -> str:
    """Why the ledger and the provider disagree about this payment's latest attempt, or ''."""
    said = provider_state(transfer)
    if transfer.amount_kes != row.amount_kes:
        return f"Paystack sent KES {transfer.amount_kes:,}; the ledger says KES {row.amount_kes:,}."
    if row.status is PaymentStatus.PAID and said is not PaymentStatus.PAID:
        return "Marked paid here, but Paystack shows the transfer did not go through."
    if row.status is not PaymentStatus.PAID and said is PaymentStatus.PAID:
        if row.status is PaymentStatus.SENDING and not _overdue(row, now):
            return ""
        return f"Paystack paid it, but here it is {row.status.label.lower()}."
    if row.status is PaymentStatus.SENDING and said is not PaymentStatus.SENDING:
        return (
            "Still sending here, but Paystack has finished with it." if _overdue(row, now) else ""
        )
    return ""


def _overdue(row: Payment, now: datetime) -> bool:
    since = row.sending_since
    if since is None:
        return True
    return now - as_utc(since) > GRACE


async def run(
    session: AsyncSession, provider: PayoutProvider | None = None, now: datetime | None = None
) -> ReconcileRun:
    """Compare the last 30 days and record what differs."""
    provider = provider or get_payout_provider()
    now = now or datetime.now(UTC)
    since = now - WINDOW
    record = ReconcileRun(provider=provider.name, status="matched")
    session.add(record)
    try:
        transfers = await provider.transfers(since)
    except Exception as exc:  # noqa: BLE001 - recorded on the run for a person to see
        record.status, record.detail = "failed", f"Could not read the provider: {exc}"[:500]
        await session.commit()
        logger.warning("reconciliation failed: %s", exc)
        return record
    if transfers is None:
        record.status = "practice"
        record.detail = "Practice mode keeps no provider records, so there is nothing to compare."
        await session.commit()
        return record

    rows = {
        r.id: r
        for r in await session.scalars(
            select(Payment).where(
                Payment.provider == provider.name,
                Payment.attempts > 0,
                or_(Payment.created_at >= since, Payment.sending_since >= since),
            )
        )
    }
    found: list[ReconcileDifference] = []

    def differ(row: Payment | None, reference: str, ledger: str, said: str, why: str) -> None:
        found.append(
            ReconcileDifference(
                payment_id=row.id if row else None,
                campaign_id=row.campaign_id if row else None,
                reference=reference[:100],
                ledger=ledger[:100],
                provider=said[:100],
                detail=why,
            )
        )

    ours = set()
    for transfer in transfers:
        match = ATTEMPT.match(transfer.reference)
        if match is None:
            continue
        payment_id, attempt = uuid.UUID(match[2]), int(match[3])
        row = rows.get(payment_id) or await session.get(Payment, payment_id)
        ours.add(transfer.reference)
        if row is None:
            differ(
                None,
                transfer.reference,
                "no payment",
                transfer.status,
                "Paystack has a transfer under this app's reference with no payment here.",
            )
        elif attempt != row.attempts:
            if provider_state(transfer) is PaymentStatus.PAID:
                differ(
                    row,
                    transfer.reference,
                    row.status.value,
                    transfer.status,
                    f"An earlier attempt (number {attempt}) was also paid out.",
                )
        elif why := _compare(row, transfer, now):
            differ(row, transfer.reference, row.status.value, transfer.status, why)

    for row in rows.values():
        reference = f"pay-{row.id}-{row.attempts}"
        if reference in ours:
            continue
        if row.status is PaymentStatus.PAID or (
            row.status is PaymentStatus.SENDING and _overdue(row, now)
        ):
            differ(
                row,
                reference,
                row.status.value,
                "none",
                "Paystack has no transfer for this payment.",
            )

    record.checked = len(rows)
    await session.flush()
    for difference in found:
        difference.run_id = record.id
    session.add_all(found)
    if found:
        record.status = "differences"
    logger.info("reconciliation: %d payments checked, %d differences", len(rows), len(found))
    await session.commit()
    return record


async def latest(session: AsyncSession) -> ReconcileRun | None:
    return await session.scalar(
        select(ReconcileRun).order_by(ReconcileRun.created_at.desc()).limit(1)
    )


async def differences(
    session: AsyncSession, run_id: uuid.UUID, campaign_id: uuid.UUID
) -> list[ReconcileDifference]:
    return list(
        await session.scalars(
            select(ReconcileDifference).where(
                ReconcileDifference.run_id == run_id,
                ReconcileDifference.campaign_id == campaign_id,
            )
        )
    )
