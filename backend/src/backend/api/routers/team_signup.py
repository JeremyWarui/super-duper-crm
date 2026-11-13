"""The public team sign-up behind a workspace's team link, the queue that decides it, and the
link itself."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from backend.api.deps import SessionDep, require
from backend.api.limits import check
from backend.api.scope import VisibleCampaign, area_of
from backend.models import OperationalGrain, RegistrationStatus, TeamRegistration, User
from backend.schemas.team_signup import (
    Approved,
    RegistrationRead,
    Rejection,
    SignupCreate,
    SignupDone,
    SignupPlace,
    SignupRead,
    TeamLink,
)
from backend.services import team_signup
from backend.services.access import workspace_access
from backend.services.errors import Refused
from backend.services.permissions import Reach, reach
from backend.services.ratelimit import RateLimit
from backend.services.targets import wards_in_area

router = APIRouter(tags=["team sign-up"])

SIGNUPS = RateLimit(limit=10, window=3600)
Approver = Annotated[User, Depends(require("team.approve"))]
TeamWriter = Annotated[User, Depends(require("team.write"))]


def _read(row: TeamRegistration, show_ids: bool) -> RegistrationRead:
    return RegistrationRead(
        id=row.id,
        role=row.role,
        full_name=row.full_name,
        phone=row.phone,
        email=row.email,
        id_number=row.id_number if show_ids else None,
        ward_name=row.ward.name if row.ward else None,
        centre_name=row.registration_centre.name if row.registration_centre else None,
        status=row.status,
        reason=row.reason,
        created_at=row.created_at,
    )


def _sees_ids(user: User) -> bool:
    return reach(user, "team.id_read") is Reach.ALL


@router.get("/team-signup/{code}/", response_model=SignupRead)
async def read_signup(code: str, session: SessionDep) -> SignupRead:
    """What the team sign-up page shows; 404 for a code that is not a workspace's."""
    campaign = await team_signup.by_code(session, code)
    wards = await wards_in_area(session, campaign)
    return SignupRead(
        campaign_title=campaign.title,
        seat_label=campaign.seat_label,
        open=(await workspace_access(session, campaign.id)).open,
        consent_wording=team_signup.CONSENT,
        mobilizer_place=(
            "centre" if campaign.operational_grain is OperationalGrain.CENTRE else "ward"
        ),
        wards=[
            SignupPlace(id=w.id, name=w.name, county_name=w.constituency.county.name) for w in wards
        ],
    )


@router.get("/team-signup/{code}/centres/", response_model=list[SignupPlace])
async def signup_centres(code: str, ward: uuid.UUID, session: SessionDep) -> list[SignupPlace]:
    """The registration centres of one of the workspace's wards."""
    campaign = await team_signup.by_code(session, code)
    return [
        SignupPlace(id=c.id, name=c.name)
        for c in await team_signup.centres_of(session, campaign, ward)
    ]


@router.post(
    "/team-signup/{code}/",
    response_model=SignupDone,
    status_code=status.HTTP_201_CREATED,
    responses={429: {"description": "Too many tries"}},
)
async def sign_up(
    code: str, payload: SignupCreate, request: Request, session: SessionDep
) -> SignupDone:
    """Sign up as a mobilizer or agent; 10 an hour per device. The login waits for approval."""
    check(SIGNUPS, request)
    campaign = await team_signup.by_code(session, code)
    if not (await workspace_access(session, campaign.id)).open:
        raise Refused("This campaign is not taking sign-ups.")
    await team_signup.register(session, campaign, payload.model_dump())
    return SignupDone(message=team_signup.SIGNED_UP)


@router.get("/campaigns/{campaign_id}/registrations/", response_model=list[RegistrationRead])
async def list_registrations(
    session: SessionDep,
    user: Approver,
    campaign: VisibleCampaign,
    status: RegistrationStatus | None = None,
) -> list[RegistrationRead]:
    """Sign-ups in the caller's reach, newest first; ID numbers only for the candidate and
    manager."""
    area = await area_of(session, user, "team.approve")
    rows = await team_signup.registrations(session, campaign.id, area, status)
    return [_read(row, _sees_ids(user)) for row in rows]


@router.post(
    "/campaigns/{campaign_id}/registrations/{registration_id}/approve/", response_model=Approved
)
async def approve(
    registration_id: uuid.UUID, session: SessionDep, user: Approver, campaign: VisibleCampaign
) -> Approved:
    """Activate the login, put the person on the workspace, and email them an invite link."""
    area = await area_of(session, user, "team.approve")
    row = await team_signup.registration(session, campaign.id, registration_id, area)
    invite, placed = await team_signup.approve(session, campaign, row, actor=user)
    row = await team_signup.registration(session, campaign.id, registration_id, None)
    return Approved(registration=_read(row, _sees_ids(user)), invite=invite, placed=placed)


@router.post(
    "/campaigns/{campaign_id}/registrations/{registration_id}/reject/",
    response_model=RegistrationRead,
)
async def reject(
    registration_id: uuid.UUID,
    payload: Rejection,
    session: SessionDep,
    user: Approver,
    campaign: VisibleCampaign,
) -> RegistrationRead:
    """Refuse a sign-up with a reason; its login is deleted."""
    area = await area_of(session, user, "team.approve")
    row = await team_signup.registration(session, campaign.id, registration_id, area)
    await team_signup.reject(session, campaign, row, payload.reason, actor=user)
    row = await team_signup.registration(session, campaign.id, registration_id, None)
    return _read(row, _sees_ids(user))


@router.get("/campaigns/{campaign_id}/team-link/", response_model=TeamLink)
async def read_team_link(
    session: SessionDep, user: Approver, campaign: VisibleCampaign
) -> TeamLink:
    return TeamLink(code=campaign.team_code)


@router.post("/campaigns/{campaign_id}/team-link/", response_model=TeamLink)
async def replace_team_link(
    session: SessionDep, user: TeamWriter, campaign: VisibleCampaign
) -> TeamLink:
    """A new team link; the old one and its QR code stop working."""
    return TeamLink(code=await team_signup.replace_code(session, campaign, actor=user))
