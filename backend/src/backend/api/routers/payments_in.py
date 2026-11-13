"""The office's list of money paid in, where M-Pesa codes that payers report are confirmed or
rejected: a workspace's contributions, and the party's contributions and nomination fees."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from backend.api.deps import NominationsOfficer, SessionDep, require
from backend.api.install import PartyOnlyRoute
from backend.api.reads import payment_in_read
from backend.api.scope import VisibleCampaign
from backend.models import Aspirant, PayInPurpose, PayInStatus, PaymentIn, User
from backend.schemas.payments_in import PaymentInRow, PayReject
from backend.services import payments_in
from backend.services.errors import NotFound, refuse_own_record

router = APIRouter(prefix="/campaigns/{campaign_id}/payments-in", tags=["payments in"])
party_router = APIRouter(
    prefix="/party/payments-in", tags=["payments in"], route_class=PartyOnlyRoute
)

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


def _party_query(user: User):
    """The party's own money; a Nominations Officer who is not the Super Admin sees fees only."""
    query = select(PaymentIn).where(PaymentIn.campaign_id.is_(None))
    if not user.is_superuser:
        query = query.where(PaymentIn.purpose == PayInPurpose.NOMINATION_FEE)
    return query


async def _party_row(session, user: User, payment_id: uuid.UUID) -> PaymentIn:
    row = await session.scalar(_party_query(user).where(PaymentIn.id == payment_id))
    if row is None:
        raise NotFound("No such payment.")
    if row.aspirant_id is not None:
        aspirant = await session.get(Aspirant, row.aspirant_id)
        if aspirant is not None:
            refuse_own_record(user, aspirant.member_id)
    return row


@party_router.get("/", response_model=list[PaymentInRow])
async def party_list(
    session: SessionDep,
    user: NominationsOfficer,
    status_filter: Annotated[PayInStatus | Literal[""], Query(alias="status")] = "",
) -> list[PaymentInRow]:
    rows = await session.scalars(_listed(_party_query(user), status_filter))
    return [payment_in_read(r, PaymentInRow) for r in rows]


@party_router.post("/{payment_id}/confirm/", response_model=PaymentInRow)
async def party_confirm(
    payment_id: uuid.UUID, session: SessionDep, user: NominationsOfficer
) -> PaymentInRow:
    row = await _party_row(session, user, payment_id)
    return payment_in_read(await payments_in.confirm(session, row, actor=user), PaymentInRow)


@party_router.post("/{payment_id}/reject/", response_model=PaymentInRow)
async def party_reject(
    payment_id: uuid.UUID, payload: PayReject, session: SessionDep, user: NominationsOfficer
) -> PaymentInRow:
    row = await _party_row(session, user, payment_id)
    return payment_in_read(
        await payments_in.reject(session, row, payload.reason, actor=user), PaymentInRow
    )
