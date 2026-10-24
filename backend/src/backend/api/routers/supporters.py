"""The supporter register of the caller's campaign."""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from backend.api.deps import SessionDep, SupporterTeam
from backend.api.scope import (
    all_rows,
    own_ground_row,
    require_campaign_mobilizer,
    require_centre_in_ward_race,
    require_own_ward,
    require_targeted_centre,
    require_visible,
    require_visible_campaign,
    require_ward_in_campaign,
    scoped,
)
from backend.models import Mobilizer, OperationalGrain, Supporter
from backend.schemas.campaign import SupporterCreate, SupporterPlace, SupporterRead
from backend.services.sms import normalise_phone

router = APIRouter(prefix="/supporters", tags=["supporters"])


@router.get("/", response_model=list[SupporterRead])
async def list_supporters(
    session: SessionDep, user: SupporterTeam, campaign: uuid.UUID | None = None
) -> list[Supporter]:
    statement = await scoped(session, user, select(Supporter), Supporter, campaign)
    return await all_rows(session, statement.order_by(Supporter.created_at.desc()))


@router.post("/", response_model=SupporterRead, status_code=status.HTTP_201_CREATED)
async def register_supporter(
    payload: SupporterCreate, session: SessionDep, user: SupporterTeam
) -> Supporter:
    """Sign someone up; a mobilizer's lands in their own ward, credited to them."""
    campaign = await require_visible_campaign(session, user, payload.campaign)
    await require_campaign_mobilizer(session, payload.campaign, payload.mobilizer)

    own = own_ground_row(user, payload.campaign)
    mobilizer_id = payload.mobilizer or (own.id if own is not None else None)
    ward_id = payload.ward or (own.ward_id if own is not None else None)
    require_own_ward(user, ward_id)
    by_centre = campaign.operational_grain is OperationalGrain.CENTRE
    if by_centre and ward_id is None:
        ward_id = campaign.ward_id
        require_own_ward(user, ward_id)
    named = await session.get(Mobilizer, mobilizer_id) if mobilizer_id else None
    centre_id = payload.registration_centre
    if by_centre and centre_id is None and named is not None and named.ward_id == ward_id:
        centre_id = named.registration_centre_id
    centre_id = centre_id if by_centre else None
    await require_ward_in_campaign(session, campaign, ward_id, centre_id)
    await require_centre_in_ward_race(session, campaign, ward_id, centre_id)
    await require_targeted_centre(session, campaign, centre_id)

    phone = normalise_phone(payload.phone) or payload.phone
    if phone and await session.scalar(
        select(Supporter.id).where(
            Supporter.campaign_id == payload.campaign, Supporter.phone == phone
        )
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "That phone number is already on this campaign's register."
        )
    supporter = Supporter(
        campaign_id=payload.campaign,
        ward_id=ward_id,
        registration_centre_id=centre_id,
        mobilizer_id=mobilizer_id,
        full_name=payload.full_name,
        phone=phone,
        support_level=payload.support_level,
        consent_given=payload.consent_given,
    )
    session.add(supporter)
    await session.commit()
    return supporter


@router.patch("/{supporter_id}/", response_model=SupporterRead)
async def place_supporter(
    supporter_id: uuid.UUID, payload: SupporterPlace, session: SessionDep, user: SupporterTeam
) -> Supporter:
    """Put a supporter at a registration centre in their ward, in a race counted by centre."""
    supporter = await require_visible(session, user, Supporter, supporter_id, "supporter")
    campaign = await require_visible_campaign(session, user, supporter.campaign_id)
    if campaign.operational_grain is not OperationalGrain.CENTRE:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Only an MCA race counts supporters per centre."
        )
    await require_ward_in_campaign(
        session, campaign, supporter.ward_id, payload.registration_centre
    )
    await require_targeted_centre(session, campaign, payload.registration_centre)
    supporter.registration_centre_id = payload.registration_centre
    await session.commit()
    return supporter
