"""The public sign-up behind an event's QR code or a campaign's link, and withdrawing again.

No login; one supporter per phone per campaign.
"""

import uuid
from dataclasses import dataclass

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.api.deps import SessionDep
from backend.api.limits import TOO_MANY_SIGNUPS, check
from backend.models import (
    Campaign,
    Event,
    EventStatus,
    OperationalGrain,
    RegistrationCentre,
    Supporter,
    SupportLevel,
    Target,
)
from backend.schemas.join import JoinCreate, JoinDone, JoinPlace, JoinRead, Withdrawn
from backend.security import new_withdraw_code
from backend.services.access import FULL, Access, workspace_access
from backend.services.campaigns import CAMPAIGN_NAMES
from backend.services.consent import WORDING, ConsentChannel
from backend.services.ratelimit import RateLimit
from backend.services.sms import require_phone
from backend.services.targets import wards_in_area

router = APIRouter(prefix="/join", tags=["join"])

# Sign-up attempts one device may send in an hour, and withdrawal attempts.
SIGNUPS = RateLimit(limit=20, window=3600)
WITHDRAWALS = RateLimit(limit=20, window=3600)
THANKS = "Thank you, you're signed up."
# The same answer for every code, so a code cannot be tested for whether it was real.
WITHDRAWN = "Done. If your details were on this campaign's register, they are gone now."


@dataclass
class Link:
    """What a sign-up code opens: an event, or a campaign's own link."""

    campaign: Campaign
    event: Event | None
    access: Access = FULL

    @property
    def open(self) -> bool:
        if not self.access.open:
            return False
        if self.event is not None:
            return self.event.signups_open and self.event.status is not EventStatus.CANCELLED
        return self.campaign.signups_open

    @property
    def channel(self) -> ConsentChannel:
        return ConsentChannel.CAMPAIGN_LINK if self.event is None else ConsentChannel.EVENT_QR


async def _link(session: SessionDep, code: str) -> Link:
    event = await session.scalar(
        select(Event)
        .where(Event.signup_code == code)
        .options(
            selectinload(Event.ward),
            selectinload(Event.campaign).options(*CAMPAIGN_NAMES),
        )
    )
    if event is not None:
        campaign = event.campaign
    else:
        campaign = await session.scalar(
            select(Campaign).where(Campaign.signup_code == code).options(*CAMPAIGN_NAMES)
        )
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This sign-up link is not valid.")
    return Link(
        campaign=campaign,
        event=event,
        access=await workspace_access(session, campaign.id),
    )


async def _places(session: SessionDep, campaign: Campaign) -> list[JoinPlace]:
    """Where a person signing up on the campaign link may say they vote."""
    if campaign.operational_grain is OperationalGrain.CENTRE:
        centres = await session.scalars(
            select(RegistrationCentre)
            .join(Target, Target.registration_centre_id == RegistrationCentre.id)
            .where(Target.campaign_id == campaign.id)
            .order_by(RegistrationCentre.name)
        )
        return [JoinPlace(id=c.id, name=c.name) for c in centres]
    return [JoinPlace(id=w.id, name=w.name) for w in await wards_in_area(session, campaign)]


@router.get("/{code}/", response_model=JoinRead)
async def read_signup(code: str, session: SessionDep) -> JoinRead:
    link = await _link(session, code)
    campaign = link.campaign
    on_campaign_link = link.event is None
    by_centre = campaign.operational_grain is OperationalGrain.CENTRE
    area = campaign.area
    return JoinRead(
        campaign_title=campaign.title,
        candidate_name=campaign.candidate_label,
        event_title=link.event.title if link.event else "",
        ward_name=link.event.ward.name if link.event else (area.name if area else ""),
        open=link.open,
        consent_wording=WORDING[link.channel],
        place=("centre" if by_centre else "ward") if on_campaign_link else None,
        places=await _places(session, campaign) if on_campaign_link else [],
    )


async def _filed_at(
    session: SessionDep, link: Link, place: uuid.UUID | None
) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    """The ward and centre a new supporter is filed under; 400 for a place off the campaign."""
    campaign = link.campaign
    by_centre = campaign.operational_grain is OperationalGrain.CENTRE
    if link.event is not None:
        return link.event.ward_id, link.event.registration_centre_id if by_centre else None
    offered = {p.id for p in await _places(session, campaign)}
    if place is not None and place not in offered:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Pick a place from the list.")
    if by_centre:
        return campaign.ward_id, place
    if place is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Pick the ward where you vote.")
    return place, None


@router.post("/{code}/", response_model=JoinDone, status_code=status.HTTP_201_CREATED)
async def sign_up(
    code: str, payload: JoinCreate, request: Request, session: SessionDep
) -> JoinDone:
    """Sign a person up; someone already on the register is left as they are.

    Every sign-up is handed a withdrawal code, a working one only for a new supporter, so
    the answer never shows whether the phone was on the register.
    """
    check(SIGNUPS, request, TOO_MANY_SIGNUPS)
    link = await _link(session, code)
    if not link.open:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Sign-ups are closed.")
    phone = require_phone(payload.phone)
    ward_id, centre_id = await _filed_at(session, link, payload.place)
    withdraw_code = new_withdraw_code()
    known = await session.scalar(
        select(Supporter.id).where(
            Supporter.campaign_id == link.campaign.id, Supporter.phone == phone
        )
    )
    if known is None:
        session.add(
            Supporter(
                campaign_id=link.campaign.id,
                ward_id=ward_id,
                registration_centre_id=centre_id,
                event_id=link.event.id if link.event else None,
                mobilizer_id=link.event.mobilizer_id if link.event else None,
                full_name=payload.full_name,
                phone=phone,
                support_level=SupportLevel.SUPPORTER,
                consent_given=True,
                consent_channel=link.channel,
                consent_wording=WORDING[link.channel],
                withdraw_code=withdraw_code,
            )
        )
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()  # the same phone signed up a moment ago
    return JoinDone(message=THANKS, withdraw_code=withdraw_code)


@router.post("/withdraw/{code}/", response_model=Withdrawn)
async def withdraw(code: str, request: Request, session: SessionDep) -> Withdrawn:
    """Take a self-signed supporter off the register; the answer is the same for any code."""
    check(WITHDRAWALS, request)
    await session.execute(delete(Supporter).where(Supporter.withdraw_code == code))
    await session.commit()
    return Withdrawn(message=WITHDRAWN)
