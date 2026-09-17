"""The supporter register of the caller's campaign."""

import uuid

from fastapi import APIRouter, Response, status
from sqlalchemy import select

from backend.api.deps import CurrentUser, SessionDep, SupporterTeam
from backend.api.scope import (
    all_rows,
    own_ground_row,
    require_campaign_mobilizer,
    require_own_ward,
    require_visible,
    require_visible_campaign,
    require_ward_in_campaign,
    scoped,
)
from backend.models import Supporter
from backend.schemas.campaign import SupporterCreate, SupporterRead

router = APIRouter(prefix="/supporters", tags=["supporters"])


@router.get("/", response_model=list[SupporterRead])
async def list_supporters(
    session: SessionDep, user: SupporterTeam, campaign: uuid.UUID | None = None
) -> list[Supporter]:
    statement = await scoped(session, user, select(Supporter), Supporter, campaign)
    return await all_rows(session, statement.order_by(Supporter.created_at.desc()))


@router.post("/", response_model=SupporterRead, status_code=status.HTTP_201_CREATED)
async def register_supporter(
    payload: SupporterCreate, session: SessionDep, user: CurrentUser
) -> Supporter:
    """Sign someone up; a mobilizer's lands in their own ward, credited to them."""
    campaign = await require_visible_campaign(session, user, payload.campaign)
    await require_campaign_mobilizer(session, payload.campaign, payload.mobilizer)

    own = own_ground_row(user, payload.campaign)
    mobilizer_id = payload.mobilizer or (own.id if own is not None else None)
    ward_id = payload.ward or (own.ward_id if own is not None else None)
    if ward_id is not None:
        require_own_ward(user, ward_id)
        await require_ward_in_campaign(session, campaign, ward_id)

    supporter = Supporter(
        campaign_id=payload.campaign,
        ward_id=ward_id,
        mobilizer_id=mobilizer_id,
        full_name=payload.full_name,
        phone=payload.phone,
        support_level=payload.support_level,
        consent_given=payload.consent_given,
    )
    session.add(supporter)
    await session.commit()
    return supporter


@router.delete("/{supporter_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supporter(
    supporter_id: uuid.UUID, session: SessionDep, user: SupporterTeam
) -> Response:
    supporter = await require_visible(session, user, Supporter, supporter_id, "supporter")
    await session.delete(supporter)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
