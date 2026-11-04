"""Payments to mobilizers for events, and the payout provider's webhook for every payment."""

import json
import logging
import uuid

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from backend.api.deps import CurrentUser, SessionDep, Writer
from backend.api.scope import (
    all_rows,
    require_campaign_mobilizer,
    require_visible_campaign,
    visible_campaign_ids,
)
from backend.models import Event, EventStatus, Mobilizer, Payment, PaymentStatus, UserRole
from backend.schemas.payment import PaymentCreate, PaymentPaid, PaymentRead, PayoutMode
from backend.services import payout_flow
from backend.services.payout_flow import OPEN
from backend.services.payouts import get_payout_provider, paystack_signed
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


async def _visible(session: SessionDep, user: Writer, payment_id: uuid.UUID) -> Payment:
    payment = await session.get(Payment, payment_id)
    if payment is None or payment.campaign_id not in await visible_campaign_ids(session, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such payment.")
    return payment


@router.get("/payout-mode/", response_model=PayoutMode)
async def payout_mode(user: CurrentUser) -> PayoutMode:
    """Whether a release moves real money."""
    provider = get_payout_provider()
    return PayoutMode(mode=provider.name, moves_money=provider.moves_money)


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
    return await payout_flow.release(session, payment, get_payout_provider(), phone)


@router.post("/{payment_id}/not-sent/", response_model=PaymentRead)
async def mark_not_sent(payment_id: uuid.UUID, session: SessionDep, user: Writer) -> Payment:
    """After checking the provider: a payment stuck in sending did not go out, so it can retry."""
    return await payout_flow.mark_not_sent(session, await _visible(session, user, payment_id))


@router.post("/{payment_id}/paid/", response_model=PaymentRead)
async def mark_paid(
    payment_id: uuid.UUID, payload: PaymentPaid, session: SessionDep, user: Writer
) -> Payment:
    """Record by hand that the money went out, under its M-Pesa or bank reference."""
    payment = await _visible(session, user, payment_id)
    return await payout_flow.mark_paid(session, payment, payload.reference)


@router.post("/{payment_id}/cancel/", response_model=PaymentRead)
async def cancel_payment(payment_id: uuid.UUID, session: SessionDep, user: Writer) -> Payment:
    return await payout_flow.cancel(session, await _visible(session, user, payment_id))


@router.post("/paystack/webhook/")
async def paystack_webhook(request: Request, session: SessionDep) -> dict[str, bool]:
    """Paystack's word on a transfer, for a party or a campaign payment; signed or refused."""
    raw = await request.body()
    if not paystack_signed(raw, {k.lower(): v for k, v in request.headers.items()}):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bad signature.")
    try:
        body = json.loads(raw)
        event, data = str(body.get("event") or ""), body.get("data") or {}
    except (ValueError, AttributeError):
        return {"applied": False}
    if not isinstance(data, dict):
        return {"applied": False}
    applied = await payout_flow.apply_transfer_event(session, event, data)
    if not applied:
        logger.info("paystack webhook %s for %s not applied", event, data.get("reference"))
    return {"applied": applied}
