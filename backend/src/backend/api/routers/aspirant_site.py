"""An aspirant installation's public candidate page and its volunteer form.

Mounted only in an aspirant installation.
"""

from fastapi import APIRouter, HTTPException, Request, status

from backend.api.deps import SessionDep
from backend.api.install import AspirantOnlyRoute
from backend.api.routers.join import _client
from backend.schemas.candidates import CandidateDetail, CandidateVolunteerCreate
from backend.schemas.join import JoinDone
from backend.services import campaign_page
from backend.services.ratelimit import RateLimit

router = APIRouter(prefix="/site", tags=["site"], route_class=AspirantOnlyRoute)

SIGNUPS = RateLimit(limit=20, window=3600)
THANKS = "Thank you. The campaign team will contact you."


@router.get("/candidate/", response_model=CandidateDetail)
async def candidate(session: SessionDep) -> CandidateDetail:
    """The candidate page the homepage shows, with the volunteer form's wards."""
    return await campaign_page.public_page(session)


@router.post("/volunteer/", response_model=JoinDone, status_code=status.HTTP_201_CREATED)
async def volunteer(
    payload: CandidateVolunteerCreate, request: Request, session: SessionDep
) -> JoinDone:
    """Sign up to volunteer for the campaign; a known phone gets the same answer."""
    if not SIGNUPS.allow(_client(request)):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many sign-ups from this device; try later."
        )
    code = await campaign_page.sign_up(session, payload)
    return JoinDone(message=THANKS, withdraw_code=code)
