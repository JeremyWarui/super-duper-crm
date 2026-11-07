"""Paying in by M-Pesa from the website: the dialog's options, a contribution, and a payment's
status while the dialog waits."""

from fastapi import APIRouter, HTTPException, Request, status

from backend.api.deps import SessionDep
from backend.api.routers.join import _client
from backend.models import PayInPurpose, PaymentIn
from backend.schemas.payments_in import PayContribution, PaymentInRead, PayOptions
from backend.services import payments_in, site
from backend.services.ratelimit import RateLimit

router = APIRouter(prefix="/pay", tags=["pay"])

STARTS = RateLimit(limit=10, window=3600)


def read(row: PaymentIn) -> PaymentInRead:
    return PaymentInRead(
        reference=row.reference,
        purpose=row.purpose,
        method=row.method,
        status=row.status,
        amount_kes=row.amount_kes,
        reason=row.reason,
        practice=row.provider == "practice",
    )


@router.get("/options/", response_model=PayOptions)
async def options(session: SessionDep) -> PayOptions:
    return PayOptions(**payments_in.options(await site.read_settings(session)))


@router.post("/contribution/", response_model=PaymentInRead, status_code=status.HTTP_201_CREATED)
async def contribute(
    payload: PayContribution, request: Request, session: SessionDep
) -> PaymentInRead:
    """A contribution from the website: to the aspirant's workspace, or to the party."""
    if not STARTS.allow(_client(request)):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many payments from this device; try later."
        )
    settings = await site.read_settings(session)
    row = await payments_in.start(
        session,
        site=settings,
        purpose=PayInPurpose.CONTRIBUTION,
        method=payload.method,
        amount_kes=payload.amount_kes,
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        mpesa_code=payload.mpesa_code,
        campaign_id=await payments_in.contribution_campaign(session, settings),
    )
    return read(row)


@router.get("/{reference}/", response_model=PaymentInRead)
async def payment(reference: str, session: SessionDep) -> PaymentInRead:
    """A payment's status by its reference, checked with Paystack when a prompt waits long."""
    row = await payments_in.by_reference(session, reference)
    return read(await payments_in.refresh(session, row))
