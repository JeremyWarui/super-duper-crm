"""Payments to mobilizers for events: scheduled, released or marked paid, or cancelled."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, update

from backend.api.deps import CurrentUser, SessionDep, Writer
from backend.api.scope import (
    all_rows,
    require_campaign_mobilizer,
    require_visible_campaign,
    visible_campaign_ids,
)
from backend.models import Event, EventStatus, Mobilizer, Payment, PaymentStatus, UserRole
from backend.models.payment import OUTCOME_UNKNOWN
from backend.schemas.payment import PaymentCreate, PaymentPaid, PaymentRead, PayoutMode
from backend.services.payouts import get_payout_provider
from backend.services.sms import normalise_phone

router = APIRouter(prefix="/payments", tags=["payments"])
logger = logging.getLogger(__name__)


@router.get("/", response_model=list[PaymentRead])
async def list_payments(
    session: SessionDep, user: CurrentUser, campaign: uuid.UUID | None = None
) -> list[Payment]:
    """Every payment of the caller's campaign; a mobilizer sees only their own."""
    statement = select(Payment).where(
        Payment.campaign_id.in_(await visible_campaign_ids(session, user))
    )
    if campaign is not None:
        statement = statement.where(Payment.campaign_id == campaign)
    if user.role is UserRole.MOBILIZER:
        profile = user.mobilizer_profile
        statement = statement.where(
            Payment.mobilizer_id == (profile.id if profile is not None else uuid.UUID(int=0))
        )
    return await all_rows(session, statement.order_by(Payment.created_at.desc()))


@router.post("/", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
async def schedule_payment(payload: PaymentCreate, session: SessionDep, user: Writer) -> Payment:
    await require_visible_campaign(session, user, payload.campaign)
    event = await session.get(Event, payload.event)
    if event is None or event.campaign_id != payload.campaign:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No such event on this campaign.")
    if event.status is EventStatus.CANCELLED:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That event was cancelled.")
    mobilizer_id = payload.mobilizer or event.mobilizer_id
    if mobilizer_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Nobody is credited with that event; name the mobilizer."
        )
    await require_campaign_mobilizer(session, payload.campaign, mobilizer_id)
    taken = await session.scalar(
        select(Payment.id).where(
            Payment.event_id == event.id,
            Payment.mobilizer_id == mobilizer_id,
            Payment.status != PaymentStatus.CANCELLED,
        )
    )
    if taken is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "That mobilizer already has a payment for this event."
        )
    mobilizer = await session.get(Mobilizer, mobilizer_id)
    payment = Payment(
        campaign_id=payload.campaign,
        event_id=event.id,
        mobilizer_id=mobilizer.id,
        recipient_name=mobilizer.full_name,
        recipient_phone=mobilizer.phone,
        event_title=event.title,
        amount_kes=payload.amount_kes,
    )
    session.add(payment)
    await session.commit()
    return payment


# A payment still waiting to go out: freshly scheduled, or a send that failed.
OPEN = (PaymentStatus.SCHEDULED, PaymentStatus.FAILED)


async def _visible(session: SessionDep, user: Writer, payment_id: uuid.UUID) -> Payment:
    payment = await session.get(Payment, payment_id)
    if payment is None or payment.campaign_id not in await visible_campaign_ids(session, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such payment.")
    return payment


async def _move(
    session: SessionDep,
    payment: Payment,
    to: PaymentStatus,
    from_: tuple[PaymentStatus, ...] = OPEN,
    **values: object,
) -> Payment:
    """Move a payment on in one statement, so two requests cannot both move it."""
    moved = await session.scalar(
        update(Payment)
        .where(Payment.id == payment.id, Payment.status.in_(from_))
        .values(status=to, **values)
        .returning(Payment.id)
    )
    if moved is None:
        await session.refresh(payment)
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"That payment is already {payment.status.label.lower()}."
        )
    await session.commit()
    await session.refresh(payment)
    return payment


@router.get("/payout-mode/", response_model=PayoutMode)
async def payout_mode(user: CurrentUser) -> PayoutMode:
    """Whether a release moves real money."""
    provider = get_payout_provider()
    return PayoutMode(mode=provider.name, moves_money=provider.moves_money)


# What a provider may report; anything else counts as an unknown outcome.
SETTLED = (PaymentStatus.PAID, PaymentStatus.SENDING, PaymentStatus.FAILED)
SEND_TIMEOUT = 30  # seconds a provider has to answer


async def _finish(session: SessionDep, payment: Payment, attempt: int, **values: object) -> Payment:
    """Record an attempt's outcome, unless a person or a later attempt has settled it since."""
    landed = await session.execute(
        update(Payment)
        .where(
            Payment.id == payment.id,
            Payment.status == PaymentStatus.SENDING,
            Payment.attempts == attempt,
        )
        .values(**values)
    )
    if landed.rowcount == 0 and "status" in values:
        # The one trace of a payment that may have gone out twice.
        logger.error(
            "payout answer for payment %s attempt %d dropped: %s %s",
            payment.id,
            attempt,
            values["status"],
            values.get("reference", ""),
        )
    await session.commit()
    await session.refresh(payment)
    return payment


@router.post("/{payment_id}/release/", response_model=PaymentRead)
async def release_payment(payment_id: uuid.UUID, session: SessionDep, user: Writer) -> Payment:
    """Send a scheduled or failed payment to the number it was scheduled for."""
    payment = await _visible(session, user, payment_id)
    if payment.status not in OPEN:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"That payment is already {payment.status.label.lower()}."
        )
    phone = normalise_phone(payment.recipient_phone)
    if phone is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"No usable phone number for {payment.recipient_name}; "
            "cancel this payment, add the number on the Mobilizers page, and schedule it again.",
        )
    mobilizer = await session.get(Mobilizer, payment.mobilizer_id) if payment.mobilizer_id else None
    current = normalise_phone(mobilizer.phone) if mobilizer is not None else phone
    if current != phone:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{payment.recipient_name}'s number changed since this was scheduled; "
            "cancel it and schedule again to pay the new number.",
        )
    provider = get_payout_provider()
    attempt = await session.scalar(
        update(Payment)
        .where(Payment.id == payment.id, Payment.status.in_(OPEN))
        .values(
            status=PaymentStatus.SENDING,
            attempts=Payment.attempts + 1,
            sending_since=datetime.now(UTC),
            provider=provider.name,
            recipient_phone=phone,
            failure_reason="",
        )
        .returning(Payment.attempts)
    )
    if attempt is None:
        await session.refresh(payment)
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"That payment is already {payment.status.label.lower()}."
        )
    await session.commit()
    await session.refresh(payment)
    try:
        result = await asyncio.wait_for(
            provider.send(
                payment_id=payment.id,
                reference=f"pay-{payment.id}-{attempt}",
                phone=phone,
                name=payment.recipient_name,
                amount_kes=payment.amount_kes,
            ),
            SEND_TIMEOUT,
        )
        outcome = PaymentStatus(result.status)
    except Exception:  # noqa: BLE001 - the money may have gone; a person settles it
        return await _finish(session, payment, attempt, failure_reason=OUTCOME_UNKNOWN)
    if outcome not in SETTLED:
        return await _finish(session, payment, attempt, failure_reason=OUTCOME_UNKNOWN)
    done = {"status": outcome, "reference": (result.reference or "")[:50], "failure_reason": ""}
    if outcome is PaymentStatus.PAID:
        done["paid_at"] = datetime.now(UTC)
    if outcome is PaymentStatus.FAILED:
        done["failure_reason"] = (result.detail or "")[:200] or "The payout provider refused it."
    return await _finish(session, payment, attempt, **done)


def _require_settleable(payment: Payment) -> None:
    """A payment still waiting on its provider is not settled by hand."""
    if payment.status is PaymentStatus.SENDING and not payment.stuck:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "That payment is still sending; wait for the payout provider to answer.",
        )


@router.post("/{payment_id}/not-sent/", response_model=PaymentRead)
async def mark_not_sent(payment_id: uuid.UUID, session: SessionDep, user: Writer) -> Payment:
    """After checking the provider: a payment stuck in sending did not go out, so it can retry."""
    payment = await _visible(session, user, payment_id)
    if payment.status is not PaymentStatus.SENDING:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Only a payment stuck in sending can be marked not sent."
        )
    _require_settleable(payment)
    return await _move(
        session,
        payment,
        PaymentStatus.FAILED,
        (PaymentStatus.SENDING,),
        failure_reason="Marked not sent after checking the provider.",
    )


@router.post("/{payment_id}/paid/", response_model=PaymentRead)
async def mark_paid(
    payment_id: uuid.UUID, payload: PaymentPaid, session: SessionDep, user: Writer
) -> Payment:
    """Record by hand that the money went out, under its M-Pesa or bank reference."""
    payment = await _visible(session, user, payment_id)
    _require_settleable(payment)
    return await _move(
        session,
        payment,
        PaymentStatus.PAID,
        (*OPEN, PaymentStatus.SENDING),
        reference=payload.reference,
        paid_at=datetime.now(UTC),
        provider="",
        failure_reason="",
    )


@router.post("/{payment_id}/cancel/", response_model=PaymentRead)
async def cancel_payment(payment_id: uuid.UUID, session: SessionDep, user: Writer) -> Payment:
    payment = await _visible(session, user, payment_id)
    return await _move(session, payment, PaymentStatus.CANCELLED)
