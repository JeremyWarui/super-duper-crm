"""Payments to mobilizers for events: scheduled, then paid or cancelled, never edited after."""

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
from backend.schemas.payment import PaymentCreate, PaymentPaid, PaymentRead

router = APIRouter(prefix="/payments", tags=["payments"])


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


async def _move(
    session: SessionDep, user: Writer, payment_id: uuid.UUID, to: PaymentStatus, **values: object
) -> Payment:
    """Move a scheduled payment on in one statement, so two requests cannot both move it."""
    payment = await session.get(Payment, payment_id)
    if payment is None or payment.campaign_id not in await visible_campaign_ids(session, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such payment.")
    moved = await session.scalar(
        update(Payment)
        .where(Payment.id == payment_id, Payment.status == PaymentStatus.SCHEDULED)
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


@router.post("/{payment_id}/paid/", response_model=PaymentRead)
async def mark_paid(
    payment_id: uuid.UUID, payload: PaymentPaid, session: SessionDep, user: Writer
) -> Payment:
    """Record that the money went out, under its M-Pesa or bank reference."""
    return await _move(
        session,
        user,
        payment_id,
        PaymentStatus.PAID,
        reference=payload.reference,
        paid_at=datetime.now(UTC),
    )


@router.post("/{payment_id}/cancel/", response_model=PaymentRead)
async def cancel_payment(payment_id: uuid.UUID, session: SessionDep, user: Writer) -> Payment:
    return await _move(session, user, payment_id, PaymentStatus.CANCELLED)
