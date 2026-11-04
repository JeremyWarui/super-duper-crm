"""The finance officer pays agents and others; the party super admin approves each payment."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from backend.api.deps import AdminUser, FinanceOfficer, SessionDep
from backend.models import PartyPayment
from backend.schemas.common import plain_text
from backend.schemas.party_payment import (
    CampaignOption,
    PartyPaymentCreate,
    PartyPaymentRead,
    PayeeOption,
    SpendReport,
)
from backend.schemas.payment import PaymentPaid
from backend.services import party_payouts, payout_flow
from backend.services.audit import record
from backend.services.payouts import get_payout_provider
from backend.services.sms import normalise_phone

router = APIRouter(prefix="/party/finance/payouts", tags=["party"])


@router.get("/", response_model=list[PartyPaymentRead])
async def list_payouts(user: FinanceOfficer, session: SessionDep) -> list[PartyPayment]:
    """Every party payment, newest first."""
    return list(
        await session.scalars(select(PartyPayment).order_by(PartyPayment.created_at.desc()))
    )


@router.post("/", response_model=PartyPaymentRead, status_code=status.HTTP_201_CREATED)
async def schedule_payout(
    payload: PartyPaymentCreate, user: FinanceOfficer, session: SessionDep
) -> PartyPayment:
    return await party_payouts.schedule(session, payload, actor=user)


@router.get("/payees/", response_model=list[PayeeOption])
async def search_payees(
    user: FinanceOfficer,
    session: SessionDep,
    q: Annotated[str, Query(min_length=2, max_length=100)],
) -> list[PayeeOption]:
    """Approved members and party volunteers matching a name or phone."""
    try:
        plain_text(q)
    except ValueError as refused:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(refused)) from None
    return await party_payouts.payees(session, q)


@router.get("/campaigns/", response_model=list[CampaignOption])
async def campaign_options(user: FinanceOfficer, session: SessionDep) -> list[CampaignOption]:
    """Approved aspirants a payment can be spent on."""
    return await party_payouts.campaigns(session)


@router.get("/spend/", response_model=SpendReport)
async def spend_report(user: FinanceOfficer, session: SessionDep) -> SpendReport:
    """Paid and still-owed money per campaign, with the party's own work last."""
    return await party_payouts.spend(session)


async def _payout(session: SessionDep, payment_id: uuid.UUID) -> PartyPayment:
    payment = await session.get(PartyPayment, payment_id)
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such payment.")
    return payment


async def _logged(
    session: SessionDep, user: FinanceOfficer, payment: PartyPayment, action: str
) -> PartyPayment:
    """The payment as it now stands, with an audit line saying who moved it."""
    record(
        session,
        actor=user,
        action=f"finance.payout.{action}",
        subject_type="party_payment",
        subject_id=payment.id,
        detail={"status": payment.status.value, "reference": payment.reference},
    )
    await session.commit()
    await session.refresh(payment)
    return payment


@router.post("/{payment_id}/approve/", response_model=PartyPaymentRead)
async def approve_payout(
    payment_id: uuid.UUID, user: AdminUser, session: SessionDep
) -> PartyPayment:
    """The party super admin lets a scheduled payment go out; never the one who scheduled it."""
    return await party_payouts.approve(session, await _payout(session, payment_id), actor=user)


@router.post("/{payment_id}/release/", response_model=PartyPaymentRead)
async def release_payout(
    payment_id: uuid.UUID, user: FinanceOfficer, session: SessionDep
) -> PartyPayment:
    """Send a scheduled or failed payment to the number it was scheduled for."""
    payment = await _payout(session, payment_id)
    party_payouts.require_approved(payment)
    phone = normalise_phone(payment.recipient_phone)
    if phone is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"No usable phone number for {payment.recipient_name}; cancel and schedule again.",
        )
    if (
        payment.status in payout_flow.OPEN
        and await party_payouts.current_phone(session, payment) != phone
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{payment.recipient_name}'s number changed since this was scheduled; "
            "cancel it and schedule again to pay the new number.",
        )
    done = await payout_flow.release(session, payment, get_payout_provider(), phone)
    return await _logged(session, user, done, "release")


@router.post("/{payment_id}/not-sent/", response_model=PartyPaymentRead)
async def mark_not_sent(
    payment_id: uuid.UUID, user: FinanceOfficer, session: SessionDep
) -> PartyPayment:
    """After checking the provider: a payment stuck in sending did not go out, so it can retry."""
    done = await payout_flow.mark_not_sent(session, await _payout(session, payment_id))
    return await _logged(session, user, done, "not_sent")


@router.post("/{payment_id}/paid/", response_model=PartyPaymentRead)
async def mark_paid(
    payment_id: uuid.UUID, payload: PaymentPaid, user: FinanceOfficer, session: SessionDep
) -> PartyPayment:
    """Record by hand that the money went out, under its M-Pesa or bank reference."""
    payment = await _payout(session, payment_id)
    party_payouts.require_approved(payment)
    done = await payout_flow.mark_paid(session, payment, payload.reference)
    return await _logged(session, user, done, "paid")


@router.post("/{payment_id}/cancel/", response_model=PartyPaymentRead)
async def cancel_payout(
    payment_id: uuid.UUID, user: FinanceOfficer, session: SessionDep
) -> PartyPayment:
    done = await payout_flow.cancel(session, await _payout(session, payment_id))
    return await _logged(session, user, done, "cancel")
