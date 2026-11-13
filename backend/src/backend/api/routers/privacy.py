"""Personal data work: requests and erasure for a workspace and the party, and closing a campaign.

Every workspace route here stays open after the campaign closes (`api/deps.py`).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select

from backend.api.deps import MembershipOfficer, SessionDep, require
from backend.api.install import PartyOnlyRoute
from backend.api.scope import VisibleCampaign
from backend.db.session import get_or_refuse
from backend.models import (
    Campaign,
    DataRequest,
    Supporter,
    TeamRegistration,
    User,
    VolunteerProfile,
)
from backend.schemas.privacy import (
    CampaignClose,
    DataRequestCreate,
    DataRequestRead,
    DataRequestUpdate,
    Erased,
    LeftTeamRead,
    Retention,
    WithdrawalLink,
)
from backend.services import privacy
from backend.services.errors import Refused, refuse_erased

router = APIRouter(prefix="/campaigns/{campaign_id}/data", tags=["data protection"])
office_router = APIRouter(
    prefix="/party/data-requests", tags=["data protection"], route_class=PartyOnlyRoute
)
Manager = Annotated[User, Depends(require("data.manage"))]
Closer = Annotated[User, Depends(require("campaign.close"))]


async def _row[T: (Supporter, VolunteerProfile, TeamRegistration)](
    session: SessionDep, model: type[T], row_id: uuid.UUID, campaign: Campaign
) -> T:
    row = await get_or_refuse(
        session, model, row_id, "person on this campaign", match={"campaign_id": campaign.id}
    )
    return row


# Data requests.


@router.get("/requests/", response_model=list[DataRequestRead])
async def list_requests(session: SessionDep, user: Manager, campaign: VisibleCampaign) -> list:
    return list(await session.scalars(privacy.requests(campaign.id)))


@router.post("/requests/", response_model=DataRequestRead, status_code=status.HTTP_201_CREATED)
async def log_request(
    payload: DataRequestCreate, session: SessionDep, user: Manager, campaign: VisibleCampaign
) -> DataRequest:
    row = privacy.log_request(session, campaign.id, payload, actor=user)
    await session.commit()
    return row


@router.patch("/requests/{request_id}/", response_model=DataRequestRead)
async def update_request(
    request_id: uuid.UUID,
    payload: DataRequestUpdate,
    session: SessionDep,
    user: Manager,
    campaign: VisibleCampaign,
) -> DataRequest:
    row = await privacy.find_request(session, campaign.id, request_id)
    privacy.update_request(row, payload, actor=user)
    await session.commit()
    return row


# Erasure on request.


@router.post("/supporters/{supporter_id}/erase/", status_code=status.HTTP_204_NO_CONTENT)
async def erase_supporter(
    supporter_id: uuid.UUID, session: SessionDep, user: Manager, campaign: VisibleCampaign
) -> None:
    supporter = await _row(session, Supporter, supporter_id, campaign)
    await privacy.erase_supporter(session, supporter, actor=user)
    await session.commit()


@router.post("/volunteers/{volunteer_id}/erase/", status_code=status.HTTP_204_NO_CONTENT)
async def erase_volunteer(
    volunteer_id: uuid.UUID, session: SessionDep, user: Manager, campaign: VisibleCampaign
) -> None:
    profile = await _row(session, VolunteerProfile, volunteer_id, campaign)
    await privacy.erase_volunteer(session, profile, actor=user)
    await session.commit()


@router.get("/left-team/", response_model=list[LeftTeamRead])
async def left_team(session: SessionDep, user: Manager, campaign: VisibleCampaign) -> list:
    """Mobilizers and agents who were turned down or have left, whose sign-up can be erased."""
    return list(await session.scalars(privacy.left_team(campaign.id)))


@router.post("/registrations/{registration_id}/erase/", status_code=status.HTTP_204_NO_CONTENT)
async def erase_registration(
    registration_id: uuid.UUID, session: SessionDep, user: Manager, campaign: VisibleCampaign
) -> None:
    registration = await _row(session, TeamRegistration, registration_id, campaign)
    await privacy.erase_registration(session, registration, actor=user)
    await session.commit()


# A supporter's withdrawal link.


@router.get("/supporters/{supporter_id}/withdrawal/", response_model=WithdrawalLink)
async def withdrawal_link(
    supporter_id: uuid.UUID, session: SessionDep, user: Manager, campaign: VisibleCampaign
) -> WithdrawalLink:
    supporter = await _row(session, Supporter, supporter_id, campaign)
    refuse_erased(supporter)
    if not supporter.withdraw_code:
        raise Refused("This supporter has no withdrawal link.")
    return WithdrawalLink(
        url=privacy.withdrawal_url(supporter.withdraw_code), can_text=bool(supporter.phone)
    )


@router.post("/supporters/{supporter_id}/withdrawal/", status_code=status.HTTP_204_NO_CONTENT)
async def text_withdrawal_link(
    supporter_id: uuid.UUID, session: SessionDep, user: Manager, campaign: VisibleCampaign
) -> None:
    supporter = await _row(session, Supporter, supporter_id, campaign)
    refuse_erased(supporter)
    if campaign.closed_at is not None:
        raise Refused(privacy.CLOSED)
    await privacy.text_withdrawal(session, supporter, campaign, actor=user)
    await session.commit()


# Closing the campaign.


async def _close_state(session: SessionDep, campaign: Campaign) -> CampaignClose:
    counts = (
        await session.execute(
            select(func.count(), func.count(Supporter.erased_at)).where(
                Supporter.campaign_id == campaign.id
            )
        )
    ).one()
    return CampaignClose(
        closed_at=campaign.closed_at,
        retention_months=campaign.retention_months,
        erase_from=privacy.erase_from(campaign),
        supporters_erased_at=campaign.supporters_erased_at,
        supporters=counts[0],
        erased=counts[1],
    )


@router.get("/close/", response_model=CampaignClose)
async def read_close(
    session: SessionDep, user: Manager, campaign: VisibleCampaign
) -> CampaignClose:
    return await _close_state(session, campaign)


@router.put("/retention/", response_model=CampaignClose)
async def set_retention(
    payload: Retention, session: SessionDep, user: Closer, campaign: VisibleCampaign
) -> CampaignClose:
    privacy.set_retention(campaign, payload.retention_months, actor=user)
    await session.commit()
    return await _close_state(session, campaign)


@router.post("/close/", response_model=CampaignClose)
async def close_campaign(
    session: SessionDep, user: Closer, campaign: VisibleCampaign
) -> CampaignClose:
    privacy.close(session, campaign, actor=user)
    await session.commit()
    return await _close_state(session, campaign)


@router.post("/erase-supporters/", response_model=Erased)
async def erase_supporters(session: SessionDep, user: Closer, campaign: VisibleCampaign) -> Erased:
    erased = await privacy.erase_supporters(session, campaign, actor=user)
    await session.commit()
    return Erased(erased=erased)


# The party's requests, kept by the Membership Officer.


@office_router.get("/", response_model=list[DataRequestRead])
async def party_requests(session: SessionDep, user: MembershipOfficer) -> list:
    return list(await session.scalars(privacy.requests(None)))


@office_router.post("/", response_model=DataRequestRead, status_code=status.HTTP_201_CREATED)
async def log_party_request(
    payload: DataRequestCreate, session: SessionDep, user: MembershipOfficer
) -> DataRequest:
    row = privacy.log_request(session, None, payload, actor=user)
    await session.commit()
    return row


@office_router.patch("/{request_id}/", response_model=DataRequestRead)
async def update_party_request(
    request_id: uuid.UUID, payload: DataRequestUpdate, session: SessionDep, user: MembershipOfficer
) -> DataRequest:
    row = await privacy.find_request(session, None, request_id)
    privacy.update_request(row, payload, actor=user)
    await session.commit()
    return row
