"""Contributions paid in by M-Pesa: a prompt on the payer's phone through Paystack, or the payer's
own Paybill or Till payment, confirmed by the campaign from its M-Pesa code."""

import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models import (
    Campaign,
    PayInMethod,
    PayInStatus,
    PaymentIn,
    SiteSettings,
    User,
)
from backend.services.audit import record
from backend.services.clock import as_utc
from backend.services.errors import NotFound, Refused
from backend.services.paystack import PaystackApi, body
from backend.services.sms import require_phone

CODE = re.compile(r"^[A-Z0-9]{10}$")
MIN_KES, MAX_KES = 10, 1_000_000
# Paystack asks for 10 seconds before a pending charge is checked.
CHECK_AFTER = timedelta(seconds=15)
DEAD = {"failed", "abandoned", "reversed"}
OPEN = (PayInStatus.PENDING, PayInStatus.TO_CONFIRM)


@dataclass
class Charge:
    status: PayInStatus
    reason: str = ""
    code: str = ""


class PayInProvider(Protocol):
    name: str

    async def charge(
        self, *, reference: str, amount_kes: int, phone: str, email: str
    ) -> Charge: ...

    async def check(self, reference: str) -> dict | None: ...


class PracticePayIns:
    """Takes no money: every prompt counts as paid at once."""

    name = "practice"

    async def charge(self, **_: object) -> Charge:
        return Charge(PayInStatus.PAID, code="PRACTICE")

    async def check(self, reference: str) -> dict | None:
        return None


class PaystackPayIns(PaystackApi):
    """An M-Pesa prompt through Paystack's Charge API; only the webhook or a check marks it paid."""

    name = "paystack"

    async def charge(self, *, reference: str, amount_kes: int, phone: str, email: str) -> Charge:
        try:
            async with self._client() as client:
                answer = await client.post(
                    "/charge",
                    json={
                        "email": email,
                        "amount": str(amount_kes * 100),
                        "currency": "KES",
                        "reference": reference,
                        "mobile_money": {"phone": phone, "provider": "mpesa"},
                        "metadata": {"purpose": "contribution"},
                    },
                )
        except httpx.HTTPError:
            # The charge may have started; the check after CHECK_AFTER settles it.
            return Charge(PayInStatus.PENDING)
        answer_body = body(answer)
        data = answer_body.get("data") if isinstance(answer_body.get("data"), dict) else {}
        state = str(data.get("status") or "")
        if answer.status_code >= 400 or state in DEAD:
            reason = str(data.get("gateway_response") or answer_body.get("message") or "")[:200]
            return Charge(PayInStatus.FAILED, reason=reason or "Paystack refused the prompt.")
        return Charge(PayInStatus.PENDING)

    async def check(self, reference: str) -> dict | None:
        try:
            async with self._client() as client:
                answer = await client.get(f"/charge/{reference}")
        except httpx.HTTPError:
            return None
        data = body(answer).get("data")
        return data if answer.status_code < 300 and isinstance(data, dict) else None


def get_payin_provider() -> PayInProvider:
    settings = get_settings()
    if settings.payin_provider == "paystack":
        return PaystackPayIns(settings.paystack_secret_key)
    return PracticePayIns()


def options(site: SiteSettings) -> dict:
    """What the payment dialog offers."""
    return {
        "prompt": True,
        "practice": get_settings().payin_provider == "practice",
        "paybill": site.mpesa_paybill,
        "account": site.mpesa_account,
        "till": site.mpesa_till,
        "instructions": site.payment_instructions,
    }


async def contribution_campaign(session: AsyncSession) -> uuid.UUID | None:
    """The campaign a website contribution belongs to; None before setup makes it."""
    return await session.scalar(select(Campaign.id).order_by(Campaign.created_at).limit(1))


def _phone(raw: str) -> str:
    refusal = "Use a Kenyan M-Pesa number, such as 0712 345678."
    phone = require_phone(raw, refusal)
    if not phone.startswith("+254"):
        raise Refused(refusal)
    return phone


def _code(raw: str) -> str:
    code = (raw or "").strip().upper()
    if not CODE.match(code):
        raise Refused("An M-Pesa code is 10 letters and numbers, such as SKL7Q2M9XA.")
    return code


async def start(
    session: AsyncSession,
    *,
    site: SiteSettings,
    method: PayInMethod,
    amount_kes: int,
    name: str,
    phone: str,
    email: str = "",
    mpesa_code: str = "",
    campaign_id: uuid.UUID | None = None,
    actor: User | None = None,
) -> PaymentIn:
    """Record a contribution and, for a prompt, send it to the payer's phone."""
    if not MIN_KES <= amount_kes <= MAX_KES:
        raise Refused(f"Give between KES {MIN_KES} and KES {MAX_KES:,}.")
    phone = _phone(phone)
    row = PaymentIn(
        method=method,
        campaign_id=campaign_id,
        amount_kes=amount_kes,
        payer_name=name.strip()[:150],
        payer_phone=phone,
        payer_email=email.strip()[:254],
        reference=f"pin-{secrets.token_hex(12)}",
        provider="manual",
    )
    if method is PayInMethod.MANUAL:
        if not (site.mpesa_paybill or site.mpesa_till):
            raise Refused("No Paybill or Till is set up, so there is nowhere to pay by code.")
        row.mpesa_code = _code(mpesa_code)
        taken = await session.scalar(
            select(PaymentIn.id).where(
                PaymentIn.mpesa_code == row.mpesa_code, PaymentIn.status != PayInStatus.REJECTED
            )
        )
        if taken is not None:
            raise Refused("That M-Pesa code is already recorded.")
        row.status = PayInStatus.TO_CONFIRM
        session.add(row)
    else:
        provider = get_payin_provider()
        contact = row.payer_email or site.contact_email
        if provider.name == "paystack" and not contact:
            raise Refused("Set the site's contact email: Paystack needs one with every prompt.")
        row.provider = provider.name
        session.add(row)
        await session.flush()
        result = await provider.charge(
            reference=row.reference,
            amount_kes=amount_kes,
            phone=phone,
            email=contact,
        )
        row.status, row.reason = result.status, result.reason
        if result.status is PayInStatus.PAID:
            await _settle(session, row, result.code)
    record(
        session,
        actor=actor,
        actor_name="public",
        action="pay_in.start",
        subject_type="payment_in",
        subject_id=row.id,
        campaign_id=campaign_id,
        detail={"method": method.value, "amount": amount_kes},
    )
    await session.commit()
    return row


async def _settle(session: AsyncSession, row: PaymentIn, code: str) -> None:
    row.status = PayInStatus.PAID
    row.paid_at = datetime.now(UTC)
    row.mpesa_code = code or row.mpesa_code


async def by_reference(session: AsyncSession, reference: str) -> PaymentIn:
    row = await session.scalar(select(PaymentIn).where(PaymentIn.reference == reference))
    if row is None:
        raise NotFound("No such payment.")
    return row


async def refresh(session: AsyncSession, row: PaymentIn) -> PaymentIn:
    """A prompt still waiting is checked with Paystack once it is old enough."""
    if row.status is PayInStatus.PENDING and row.provider == "paystack":
        created = as_utc(row.created_at)
        if datetime.now(UTC) - created >= CHECK_AFTER:
            data = await get_payin_provider().check(row.reference)
            if data is not None and await _apply(session, row, data):
                await session.commit()
    return row


async def _apply(session: AsyncSession, row: PaymentIn, data: dict) -> bool:
    """Settle a waiting prompt from Paystack's charge data; False when nothing changed."""
    if row.status is not PayInStatus.PENDING:
        return False
    state = str(data.get("status") or "")
    if state == "success":
        amount = int(data.get("amount") or 0)
        if amount != row.amount_kes * 100 or str(data.get("currency") or "") != "KES":
            row.status = PayInStatus.FAILED
            row.reason = "Paystack's amount or currency does not match this payment."
        else:
            await _settle(session, row, str(data.get("receipt_number") or "")[:20])
    elif state in DEAD:
        row.status = PayInStatus.FAILED
        row.reason = str(data.get("gateway_response") or f"The payment {state}.")[:300]
    else:
        return False
    record(
        session,
        actor=None,
        actor_name="paystack",
        action=f"pay_in.{row.status.value}",
        subject_type="payment_in",
        subject_id=row.id,
        campaign_id=row.campaign_id,
        detail={"reference": row.reference},
    )
    return True


async def apply_charge_event(session: AsyncSession, event: str, data: dict) -> bool:
    """A signed Paystack webhook for a charge; a replay or an unknown reference changes nothing."""
    if not event.startswith("charge."):
        return False
    row = await session.scalar(
        select(PaymentIn).where(PaymentIn.reference == str(data.get("reference") or ""))
    )
    if row is None or not await _apply(session, row, data):
        return False
    await session.commit()
    return True


async def confirm(session: AsyncSession, row: PaymentIn, *, actor: User) -> PaymentIn:
    """The campaign found the code on its M-Pesa statement."""
    if row.status is not PayInStatus.TO_CONFIRM:
        raise Refused("Only a code waiting for confirmation is confirmed.")
    row.decided_by_id, row.decided_at = actor.id, datetime.now(UTC)
    await _settle(session, row, row.mpesa_code)
    record(
        session,
        actor=actor,
        action="pay_in.confirm",
        subject_type="payment_in",
        subject_id=row.id,
        campaign_id=row.campaign_id,
        detail={"code": row.mpesa_code, "amount": row.amount_kes},
    )
    await session.commit()
    return row


async def reject(session: AsyncSession, row: PaymentIn, reason: str, *, actor: User) -> PaymentIn:
    """The code is not on the statement, or the amount is wrong."""
    if row.status is not PayInStatus.TO_CONFIRM:
        raise Refused("Only a code waiting for confirmation is rejected.")
    if not reason.strip():
        raise Refused("Say why the code is rejected.")
    row.status, row.reason = PayInStatus.REJECTED, reason.strip()[:300]
    row.decided_by_id, row.decided_at = actor.id, datetime.now(UTC)
    record(
        session,
        actor=actor,
        action="pay_in.reject",
        subject_type="payment_in",
        subject_id=row.id,
        campaign_id=row.campaign_id,
        detail={"code": row.mpesa_code},
    )
    await session.commit()
    return row
