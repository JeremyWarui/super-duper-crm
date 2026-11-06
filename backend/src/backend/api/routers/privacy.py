"""Personal data work: requests and erasure for a workspace and the party, and closing a campaign.

Every workspace route here stays open after the campaign closes (`api/deps.py`).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import func, select

from backend.api.deps import MembershipOfficer, SessionDep, require
from backend.api.install import PartyOnlyRoute
from backend.api.scope import require_visible_campaign
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
from backend.services.errors import NotFound, Refused

router = APIRouter(prefix="/campaigns/{campaign_id}/data", tags=["data protection"])
office_router = APIRouter(
    prefix="/party/data-requests", tags=["data protection"], route_class=PartyOnlyRoute
)
Manager = Annotated[User, Depends(require("data.manage"))]
Closer = Annotated[User, Depends(require("campaign.close"))]


async def _row[T: (Supporter, VolunteerProfile, TeamRegistration)](
    session: SessionDep, model: type[T], row_id: uuid.UUID, campaign: Campaign
) -> T:
    row = await session.get(model, row_id)
    if row is None or row.campaign_id != campaign.id:
        raise NotFound("No such person on this campaign.")
    return row


# Data requests.


@router.get("/requests/", response_model=list[DataRequestRead])
async def list_requests(campaign_id: uuid.UUID, session: SessionDep, user: Manager) -> list:
    campaign = await require_visible_campaign(session, user, campaign_id)
    return list(await session.scalars(privacy.requests(campaign.id)))


@router.post("/requests/", response_model=DataRequestRead, status_code=status.HTTP_201_CREATED)
async def log_request(
    campaign_id: uuid.UUID, payload: DataRequestCreate, session: SessionDep, user: Manager
) -> DataRequest:
    campaign = await require_visible_campaign(session, user, campaign_id)
    row = privacy.log_request(session, campaign.id, payload, actor=user)
    await session.commit()
    return row


@router.patch("/requests/{request_id}/", response_model=DataRequestRead)
async def update_request(
    campaign_id: uuid.UUID,
    request_id: uuid.UUID,
    payload: DataRequestUpdate,
    session: SessionDep,
    user: Manager,
) -> DataRequest:
    campaign = await require_visible_campaign(session, user, campaign_id)
    row = await privacy.find_request(session, campaign.id, request_id)
    privacy.update_request(row, payload, actor=user)
    await session.commit()
    return row


# Erasure on request.


@router.post("/supporters/{supporter_id}/erase/", status_code=status.HTTP_204_NO_CONTENT)
async def erase_supporter(
    campaign_id: uuid.UUID, supporter_id: uuid.UUID, session: SessionDep, user: Manager
) -> Response:
    campaign = await require_visible_campaign(session, user, campaign_id)
    supporter = await _row(session, Supporter, supporter_id, campaign)
    await privacy.erase_supporter(session, supporter, actor=user)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/volunteers/{volunteer_id}/erase/", status_code=status.HTTP_204_NO_CONTENT)
async def erase_volunteer(
    campaign_id: uuid.UUID, volunteer_id: uuid.UUID, session: SessionDep, user: Manager
) -> Response:
    campaign = await require_visible_campaign(session, user, campaign_id)
    profile = await _row(session, VolunteerProfile, volunteer_id, campaign)
    await privacy.erase_volunteer(session, profile, actor=user)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/left-team/", response_model=list[LeftTeamRead])
async def left_team(campaign_id: uuid.UUID, session: SessionDep, user: Manager) -> list:
    """Mobilizers and agents who were turned down or have left, whose sign-up can be erased."""
    campaign = await require_visible_campaign(session, user, campaign_id)
    return list(await session.scalars(privacy.left_team(campaign.id)))


@router.post("/registrations/{registration_id}/erase/", status_code=status.HTTP_204_NO_CONTENT)
async def erase_registration(
    campaign_id: uuid.UUID, registration_id: uuid.UUID, session: SessionDep, user: Manager
) -> Response:
    campaign = await require_visible_campaign(session, user, campaign_id)
    registration = await _row(session, TeamRegistration, registration_id, campaign)
    await privacy.erase_registration(session, registration, actor=user)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# A supporter's withdrawal link.


@router.get("/supporters/{supporter_id}/withdrawal/", response_model=WithdrawalLink)
async def withdrawal_link(
    campaign_id: uuid.UUID, supporter_id: uuid.UUID, session: SessionDep, user: Manager
) -> WithdrawalLink:
    campaign = await require_visible_campaign(session, user, campaign_id)
    supporter = await _row(session, Supporter, supporter_id, campaign)
    privacy.refuse_erased(supporter)
    if not supporter.withdraw_code:
        raise Refused("This supporter has no withdrawal link.")
    return WithdrawalLink(
        url=privacy.withdrawal_url(supporter.withdraw_code), can_text=bool(supporter.phone)
    )


@router.post("/supporters/{supporter_id}/withdrawal/", status_code=status.HTTP_204_NO_CONTENT)
async def text_withdrawal_link(
    campaign_id: uuid.UUID, supporter_id: uuid.UUID, session: SessionDep, user: Manager
) -> Response:
    campaign = await require_visible_campaign(session, user, campaign_id)
    supporter = await _row(session, Supporter, supporter_id, campaign)
    privacy.refuse_erased(supporter)
    if campaign.closed_at is not None:
        raise Refused(privacy.CLOSED)
    await privacy.text_withdrawal(session, supporter, campaign, actor=user)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
async def read_close(campaign_id: uuid.UUID, session: SessionDep, user: Manager) -> CampaignClose:
    campaign = await require_visible_campaign(session, user, campaign_id)
    return await _close_state(session, campaign)


@router.put("/retention/", response_model=CampaignClose)
async def set_retention(
    campaign_id: uuid.UUID, payload: Retention, session: SessionDep, user: Closer
) -> CampaignClose:
    campaign = await require_visible_campaign(session, user, campaign_id)
    privacy.set_retention(campaign, payload.retention_months, actor=user)
    await session.commit()
    return await _close_state(session, campaign)


@router.post("/close/", response_model=CampaignClose)
async def close_campaign(
    campaign_id: uuid.UUID, session: SessionDep, user: Closer
) -> CampaignClose:
    campaign = await require_visible_campaign(session, user, campaign_id)
    privacy.close(session, campaign, actor=user)
    await session.commit()
    return await _close_state(session, campaign)


@router.post("/erase-supporters/", response_model=Erased)
async def erase_supporters(campaign_id: uuid.UUID, session: SessionDep, user: Closer) -> Erased:
    campaign = await require_visible_campaign(session, user, campaign_id)
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
