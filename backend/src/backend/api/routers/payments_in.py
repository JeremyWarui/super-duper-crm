"""The campaign's contributions, where M-Pesa codes that payers report are confirmed or
rejected."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from backend.api.deps import SessionDep, require
from backend.api.reads import payment_in_read
from backend.api.scope import VisibleCampaign
from backend.models import PayInStatus, PaymentIn, User
from backend.schemas.payments_in import PaymentInRow, PayReject
from backend.services import payments_in
from backend.services.errors import NotFound

router = APIRouter(prefix="/campaigns/{campaign_id}/payments-in", tags=["payments in"])

Treasurer = Annotated[User, Depends(require("contributions.read"))]
LIMIT = 200


def _listed(query, status_filter: PayInStatus | Literal[""]):
    """Newest first; an empty status lists every status."""
    if status_filter:
        query = query.where(PaymentIn.status == status_filter)
    return query.order_by(PaymentIn.created_at.desc()).limit(LIMIT)


async def _campaign_row(session, campaign_id: uuid.UUID, payment_id: uuid.UUID) -> PaymentIn:
    row = await session.get(PaymentIn, payment_id)
    if row is None or row.campaign_id != campaign_id:
        raise NotFound("No such payment.")
    return row


@router.get("/", response_model=list[PaymentInRow])
async def campaign_list(
    session: SessionDep,
    user: Treasurer,
    campaign: VisibleCampaign,
    status_filter: Annotated[PayInStatus | Literal[""], Query(alias="status")] = "",
) -> list[PaymentInRow]:
    """The workspace's contributions, newest first."""
    rows = await session.scalars(
        _listed(select(PaymentIn).where(PaymentIn.campaign_id == campaign.id), status_filter)
    )
    return [payment_in_read(r, PaymentInRow) for r in rows]


@router.post("/{payment_id}/confirm/", response_model=PaymentInRow)
async def campaign_confirm(
    payment_id: uuid.UUID, session: SessionDep, user: Treasurer, campaign: VisibleCampaign
) -> PaymentInRow:
    row = await _campaign_row(session, campaign.id, payment_id)
    return payment_in_read(await payments_in.confirm(session, row, actor=user), PaymentInRow)


@router.post("/{payment_id}/reject/", response_model=PaymentInRow)
async def campaign_reject(
    payment_id: uuid.UUID,
    payload: PayReject,
    session: SessionDep,
    user: Treasurer,
    campaign: VisibleCampaign,
) -> PaymentInRow:
    row = await _campaign_row(session, campaign.id, payment_id)
    return payment_in_read(
        await payments_in.reject(session, row, payload.reason, actor=user), PaymentInRow
    )
