"""Payments to mobilizers and agents for done assignments, routed to their approver, and the
payout provider's webhook."""

import json
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.api.deps import CurrentUser, SessionDep, require
from backend.api.scope import (
    all_rows,
    area_ids,
    require_in_area,
    require_visible_campaign,
    visible_campaign_ids,
)
from backend.models import (
    Agent,
    Assignment,
    AssignmentStatus,
    Event,
    Mobilizer,
    Payment,
    PaymentStatus,
    User,
    UserRole,
)
from backend.schemas.payment import (
    PaymentCreate,
    PaymentDecline,
    PaymentPaid,
    PaymentRead,
    PayoutMode,
)
from backend.services import assignments, payment_routing, payout_flow
from backend.services.audit import record
from backend.services.payout_flow import OPEN
from backend.services.payouts import get_payout_provider, paystack_signed
from backend.services.permissions import Reach, reach
from backend.services.sms import normalise_phone

router = APIRouter(prefix="/payments", tags=["payments"])
logger = logging.getLogger(__name__)
Reader = Annotated[User, Depends(require("payments.read"))]
Scheduler = Annotated[User, Depends(require("payments.schedule"))]
Approver = Annotated[User, Depends(require("payments.approve"))]


@router.get("/", response_model=list[PaymentRead])
async def list_payments(
    session: SessionDep, user: Reader, campaign: uuid.UUID | None = None
) -> list[Payment]:
    """The caller's campaign's payments: all of them, a coordinator's for work in their area,
    or a mobilizer's or agent's own."""
    statement = select(Payment).where(
        Payment.campaign_id.in_(await visible_campaign_ids(session, user))
    )
    if campaign is not None:
        statement = statement.where(Payment.campaign_id == campaign)
    match reach(user, "payments.read"):
        case Reach.AREA:
            area = await area_ids(session, user)
            in_area = select(Assignment.id).where(
                area.where(Assignment.ward_id, Assignment.registration_centre_id)
            )
            events = select(Event.id).where(area.where(Event.ward_id, Event.registration_centre_id))
            statement = statement.where(
                or_(
                    Payment.assignment_id.in_(in_area),
                    and_(Payment.assignment_id.is_(None), Payment.event_id.in_(events)),
                )
            )
        case Reach.OWN if user.role is UserRole.MOBILIZER:
            profile = user.mobilizer_profile
            statement = statement.where(
                Payment.mobilizer_id == (profile.id if profile is not None else uuid.UUID(int=0))
            )
        case Reach.OWN:
            agent = await session.scalar(select(Agent.id).where(Agent.user_id == user.id))
            statement = statement.where(Payment.agent_id == (agent or uuid.UUID(int=0)))
    return await all_rows(session, statement.order_by(Payment.created_at.desc()))


@router.post("/", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
async def schedule_payment(payload: PaymentCreate, session: SessionDep, user: Scheduler) -> Payment:
    """Pay a done assignment, once, to its mobilizer or agent; routed to its approver."""
    found = await session.get(Assignment, payload.assignment)
    if found is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No such assignment.")
    campaign = await require_visible_campaign(session, user, found.campaign_id)
    work = await assignments.assignment(session, campaign.id, found.id, None)
    await require_in_area(
        session, user, "payments.schedule", work.ward_id, work.registration_centre_id
    )
    if work.status is not AssignmentStatus.DONE:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Only an assignment marked done can be paid."
        )
    approver = payment_routing.approver_for(user, campaign)
    taken = await session.scalar(
        select(Payment.id).where(
            Payment.assignment_id == work.id, Payment.status != PaymentStatus.CANCELLED
        )
    )
    if taken is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That assignment already has a payment.")
    if work.mobilizer is not None:
        name, phone = work.mobilizer.full_name, work.mobilizer.phone
    else:
        name = work.agent.user.full_name or work.agent.user.username
        phone = work.agent.user.phone
    payment = Payment(
        campaign_id=campaign.id,
        assignment_id=work.id,
        event_id=work.event_id,
        mobilizer_id=work.mobilizer_id,
        agent_id=work.agent_id,
        recipient_name=name,
        recipient_phone=phone,
        event_title=work.label,
        amount_kes=work.amount_kes,
        scheduled_by_id=user.id,
        approver_role=approver,
    )
    session.add(payment)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "That assignment already has a payment."
        ) from None
    record(
        session,
        actor=user,
        action="payment.schedule",
        subject_type="payment",
        subject_id=payment.id,
        campaign_id=campaign.id,
        detail={"amount_kes": payment.amount_kes, "approver": approver.value},
    )
    await session.commit()
    return payment


async def _visible(session: SessionDep, user: User, payment_id: uuid.UUID) -> Payment:
    payment = await session.get(Payment, payment_id)
    if payment is None or payment.campaign_id not in await visible_campaign_ids(session, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such payment.")
    return payment


async def _approvable(session: SessionDep, user: User, payment_id: uuid.UUID) -> Payment:
    """A payment this caller may approve: the role routing names, never its own scheduling."""
    payment = await _visible(session, user, payment_id)
    if not payment_routing.may_approve(user, payment):
        if payment.scheduled_by_id == user.id:
            detail = "You scheduled this payment, so someone else approves it."
        else:
            role = payment_routing.approver_of(payment).label
            detail = f"This payment is for the {role} to approve."
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail)
    return payment


def _decided(session: SessionDep, user: User, payment: Payment, action: str, **detail) -> None:
    record(
        session,
        actor=user,
        action=action,
        subject_type="payment",
        subject_id=payment.id,
        campaign_id=payment.campaign_id,
        detail=detail or None,
    )


@router.get("/payout-mode/", response_model=PayoutMode)
async def payout_mode(user: CurrentUser) -> PayoutMode:
    """Whether a release moves real money."""
    provider = get_payout_provider()
    return PayoutMode(mode=provider.name, moves_money=provider.moves_money)


@router.post("/{payment_id}/release/", response_model=PaymentRead)
async def release_payment(payment_id: uuid.UUID, session: SessionDep, user: Approver) -> Payment:
    """Approve a scheduled or failed payment and send it to the number it was scheduled for."""
    payment = await _approvable(session, user, payment_id)
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
    current = phone
    if payment.mobilizer_id:
        mobilizer = await session.get(Mobilizer, payment.mobilizer_id)
        current = normalise_phone(mobilizer.phone) if mobilizer is not None else phone
    elif payment.agent_id:
        agent = await session.scalar(
            select(Agent).where(Agent.id == payment.agent_id).options(selectinload(Agent.user))
        )
        current = normalise_phone(agent.user.phone) if agent is not None else phone
    if current != phone:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{payment.recipient_name}'s number changed since this was scheduled; "
            "cancel it and schedule again to pay the new number.",
        )
    released = await payout_flow.release(session, payment, get_payout_provider(), phone)
    # Recorded once the release has claimed the payment, so a second approver racing it fails
    # before writing an approval.
    released.approved_by_id = user.id
    _decided(session, user, released, "payment.approve")
    await session.commit()
    return released


@router.post("/{payment_id}/not-sent/", response_model=PaymentRead)
async def mark_not_sent(payment_id: uuid.UUID, session: SessionDep, user: Approver) -> Payment:
    """After checking the provider: a payment stuck in sending did not go out, so it can retry."""
    payment = await _approvable(session, user, payment_id)
    _decided(session, user, payment, "payment.not_sent")
    return await payout_flow.mark_not_sent(session, payment)


@router.post("/{payment_id}/paid/", response_model=PaymentRead)
async def mark_paid(
    payment_id: uuid.UUID, payload: PaymentPaid, session: SessionDep, user: Approver
) -> Payment:
    """Record by hand that the money went out, under its M-Pesa or bank reference."""
    payment = await _approvable(session, user, payment_id)
    payment.approved_by_id = user.id
    _decided(session, user, payment, "payment.mark_paid", reference=payload.reference)
    return await payout_flow.mark_paid(session, payment, payload.reference)


@router.post("/{payment_id}/decline/", response_model=PaymentRead)
async def decline_payment(
    payment_id: uuid.UUID, payload: PaymentDecline, session: SessionDep, user: Approver
) -> Payment:
    """Refuse a payment with a reason; its assignment can be paid by a new one."""
    payment = await _approvable(session, user, payment_id)
    _decided(session, user, payment, "payment.decline", reason=payload.reason)
    return await payout_flow.move(
        session, payment, PaymentStatus.CANCELLED, failure_reason=payload.reason
    )


@router.post("/paystack/webhook/")
async def paystack_webhook(request: Request, session: SessionDep) -> dict[str, bool]:
    """Paystack's word on a campaign payment's transfer; signed or refused."""
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
