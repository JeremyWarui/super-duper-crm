"""The supporter register of the caller's campaign."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import Select, func, or_, select

from backend.api.deps import SessionDep, require
from backend.api.scope import (
    NOBODY,
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
from backend.models import Mobilizer, OperationalGrain, Supporter, SupportLevel, User, UserRole
from backend.schemas.campaign import (
    ConsentWording,
    SupporterCounts,
    SupporterCreate,
    SupporterPlace,
    SupporterRead,
)
from backend.security import new_withdraw_code
from backend.services import privacy
from backend.services.consent import SMS_WORDING, WORDING, ConsentChannel
from backend.services.errors import PHONE_ON_REGISTER, NotFound, Refused, refuse_erased
from backend.services.sms import normalise_phone

router = APIRouter(prefix="/supporters", tags=["supporters"])
Reader = Annotated[User, Depends(require("supporters.read"))]
Writer = Annotated[User, Depends(require("supporters.write"))]

# The most rows one call returns.
PAGE_MAX = 200


def _own_only(statement: Select, user: User) -> Select:
    """A mobilizer's view: only the contacts they signed up."""
    if user.role is not UserRole.MOBILIZER:
        return statement
    profile = user.mobilizer_profile
    return statement.where(Supporter.mobilizer_id == (profile.id if profile else NOBODY))


async def _visible_rows(
    session: SessionDep, user: User, statement: Select, campaign: uuid.UUID | None
) -> Select:
    scoped_statement = await scoped(
        session, user, statement, Supporter, campaign, "supporters.read"
    )
    return _own_only(scoped_statement, user)


def _matching(statement: Select, q: str | None) -> Select:
    """Rows whose name or phone contains `q`, ignoring case."""
    needle = (q or "").strip()
    if not needle:
        return statement
    escaped = needle.replace("!", "!!").replace("%", "!%").replace("_", "!_")
    like = f"%{escaped}%"
    return statement.where(
        or_(Supporter.full_name.ilike(like, escape="!"), Supporter.phone.ilike(like, escape="!"))
    )


@router.get("/", response_model=list[SupporterRead])
async def list_supporters(
    session: SessionDep,
    user: Reader,
    campaign: uuid.UUID | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    support_level: SupportLevel | None = None,
    limit: Annotated[int, Query(ge=1, le=PAGE_MAX)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Supporter]:
    """Newest first, `limit` rows at a time."""
    statement = _matching(await _visible_rows(session, user, select(Supporter), campaign), q)
    if support_level is not None:
        statement = statement.where(Supporter.support_level == support_level)
    statement = statement.order_by(Supporter.created_at.desc(), Supporter.id)
    return await all_rows(session, statement.offset(offset).limit(limit))


@router.get("/summary/", response_model=SupporterCounts)
async def count_supporters(
    session: SessionDep,
    user: Reader,
    campaign: uuid.UUID | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> SupporterCounts:
    level = Supporter.support_level
    counts = select(
        func.count(),
        func.count().filter(level == SupportLevel.SUPPORTER),
        func.count().filter(level == SupportLevel.UNDECIDED),
        func.count().filter(Supporter.consent_given.is_(False)),
    ).select_from(Supporter)
    statement = _matching(await _visible_rows(session, user, counts, campaign), q)
    total, supporters, undecided, missing = (await session.execute(statement)).one()
    return SupporterCounts(
        total=total, supporters=supporters, undecided=undecided, consent_missing=missing
    )


@router.get("/consent-wording/", response_model=ConsentWording)
async def consent_wording(user: Writer) -> ConsentWording:
    """The wording a mobilizer's sign-up form shows and the server records."""
    return ConsentWording(
        consent_wording=WORDING[ConsentChannel.MOBILIZER],
        sms_consent_wording=SMS_WORDING[ConsentChannel.MOBILIZER],
    )


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
    require_centre_in_ward_race(campaign, centre_id)
    await require_targeted_centre(session, campaign, centre_id)

    phone = normalise_phone(payload.phone) or payload.phone
    if phone and await session.scalar(
        select(Supporter.id).where(
            Supporter.campaign_id == payload.campaign, Supporter.phone == phone
        )
    ):
        raise Refused(PHONE_ON_REGISTER)
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
        sms_consent=payload.sms_consent,
        sms_consent_wording=SMS_WORDING[ConsentChannel.MOBILIZER] if payload.sms_consent else None,
        withdraw_code=new_withdraw_code(),
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
    refuse_erased(supporter)
    if user.role is UserRole.MOBILIZER and supporter.mobilizer_id != (
        user.mobilizer_profile.id if user.mobilizer_profile else NOBODY
    ):
        raise NotFound("No such supporter.")
    campaign = await require_visible_campaign(session, user, supporter.campaign_id)
    if campaign.operational_grain is not OperationalGrain.CENTRE:
        raise Refused("Only an MCA race files contacts per centre.")
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
