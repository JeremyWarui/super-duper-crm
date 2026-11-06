"""The supporter register of the caller's campaign."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from backend.api.deps import SessionDep, require
from backend.api.scope import (
    all_rows,
    own_ground_row,
    require_campaign_mobilizer,
    require_centre_in_ward_race,
    require_in_area,
    require_mobilizer_in_area,
    require_targeted_centre,
    require_visible,
    require_visible_campaign,
    require_ward_in_campaign,
    scoped,
)
from backend.models import Mobilizer, OperationalGrain, Supporter, User
from backend.schemas.campaign import (
    ConsentWording,
    SupporterCreate,
    SupporterPlace,
    SupporterRead,
)
from backend.services import privacy
from backend.services.consent import WORDING, ConsentChannel
from backend.services.sms import normalise_phone

router = APIRouter(prefix="/supporters", tags=["supporters"])
Reader = Annotated[User, Depends(require("supporters.read"))]
Writer = Annotated[User, Depends(require("supporters.write"))]


@router.get("/", response_model=list[SupporterRead])
async def list_supporters(
    session: SessionDep, user: Reader, campaign: uuid.UUID | None = None
) -> list[Supporter]:
    statement = await scoped(
        session, user, select(Supporter), Supporter, campaign, "supporters.read"
    )
    return await all_rows(session, statement.order_by(Supporter.created_at.desc()))


@router.get("/consent-wording/", response_model=ConsentWording)
async def consent_wording(user: Writer) -> ConsentWording:
    """The wording a mobilizer's sign-up form shows and the server records."""
    return ConsentWording(consent_wording=WORDING[ConsentChannel.MOBILIZER])


@router.post("/", response_model=SupporterRead, status_code=status.HTTP_201_CREATED)
async def register_supporter(
    payload: SupporterCreate, session: SessionDep, user: Writer
) -> Supporter:
    """Sign someone up; a mobilizer's lands in their own ward, credited to them."""
    campaign = await require_visible_campaign(session, user, payload.campaign)
    await require_campaign_mobilizer(session, payload.campaign, payload.mobilizer)
    await require_mobilizer_in_area(session, user, "supporters.write", payload.mobilizer)

    own = own_ground_row(user, payload.campaign)
    mobilizer_id = payload.mobilizer or (own.id if own is not None else None)
    ward_id = payload.ward or (own.ward_id if own is not None else None)
    by_centre = campaign.operational_grain is OperationalGrain.CENTRE
    if by_centre and ward_id is None:
        ward_id = campaign.ward_id
    named = await session.get(Mobilizer, mobilizer_id) if mobilizer_id else None
    centre_id = payload.registration_centre
    if by_centre and centre_id is None and named is not None and named.ward_id == ward_id:
        centre_id = named.registration_centre_id
    centre_id = centre_id if by_centre else None
    await require_in_area(session, user, "supporters.write", ward_id, centre_id)
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
        consent_channel=ConsentChannel.MOBILIZER,
        consent_wording=WORDING[ConsentChannel.MOBILIZER],
        withdraw_code=privacy.new_code(),
    )
    session.add(supporter)
    await session.flush()
    if phone:
        await privacy.text_withdrawal(session, supporter, campaign, actor=user)
    await session.commit()
    return supporter


@router.patch("/{supporter_id}/", response_model=SupporterRead)
async def place_supporter(
    supporter_id: uuid.UUID, payload: SupporterPlace, session: SessionDep, user: Writer
) -> Supporter:
    """Put a supporter at a registration centre in their ward, in a race counted by centre."""
    supporter = await require_visible(
        session, user, Supporter, supporter_id, "supporter", "supporters.write"
    )
    privacy.refuse_erased(supporter)
    campaign = await require_visible_campaign(session, user, supporter.campaign_id)
    if campaign.operational_grain is not OperationalGrain.CENTRE:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Only an MCA race counts supporters per centre."
        )
    await require_ward_in_campaign(
        session, campaign, supporter.ward_id, payload.registration_centre
    )
    await require_targeted_centre(session, campaign, payload.registration_centre)
    await require_in_area(
        session, user, "supporters.write", supporter.ward_id, payload.registration_centre
    )
    supporter.registration_centre_id = payload.registration_centre
    await session.commit()
    return supporter
