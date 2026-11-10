"""The website's candidates: the directory, each profile, and its "Support" volunteer form."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status

from backend.api.deps import SessionDep, Today
from backend.api.install import PartyOnlyRoute
from backend.api.limits import check
from backend.models import Seat
from backend.schemas.candidates import CandidateCard, CandidateDetail, CandidateVolunteerCreate
from backend.schemas.join import JoinDone, Withdrawn
from backend.services import campaign_volunteers
from backend.services import candidates as service
from backend.services.ratelimit import RateLimit

router = APIRouter(prefix="/candidates", tags=["candidates"])
# Mounted in every installation; party_router only in a party installation.
party_router = APIRouter(prefix="/candidates", tags=["candidates"], route_class=PartyOnlyRoute)

SIGNUPS = RateLimit(limit=20, window=3600)
WITHDRAWALS = RateLimit(limit=20, window=3600)
THANKS = "Thank you. The campaign team will contact you."
# The same answer for every code, so a code cannot be tested for whether it was real.
WITHDRAWN = "Done. If you were on this campaign's volunteer list, you are off it now."


@party_router.get("/", response_model=list[CandidateCard])
async def list_candidates(
    session: SessionDep,
    seat: Annotated[str, Query(max_length=20)] = "",
    county: Annotated[str, Query(max_length=40)] = "",
    q: Annotated[str, Query(max_length=100)] = "",
) -> list[CandidateCard]:
    """Approved aspirants whose profile the party has published; an empty filter means any."""
    try:
        seat_value = Seat(seat).value if seat else None
        county_id = uuid.UUID(county) if county else None
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown seat or county.") from None
    return await service.candidates(session, seat=seat_value, county=county_id, q=q)


@router.post("/volunteer/withdraw/{code}/", response_model=Withdrawn)
async def withdraw(code: str, request: Request, session: SessionDep) -> Withdrawn:
    """Take a volunteer off a campaign's list; the answer is the same for any code."""
    check(WITHDRAWALS, request)
    await campaign_volunteers.withdraw(session, code)
    return Withdrawn(message=WITHDRAWN)


@router.get("/{slug}/", response_model=CandidateDetail)
async def read_candidate(slug: str, session: SessionDep, today: Today) -> CandidateDetail:
    return await service.candidate(session, slug, today)


@router.post("/{slug}/volunteer/", response_model=JoinDone, status_code=status.HTTP_201_CREATED)
async def volunteer(
    slug: str,
    payload: CandidateVolunteerCreate,
    request: Request,
    session: SessionDep,
) -> JoinDone:
    """Sign up to volunteer for the candidate's campaign; a known phone gets the same answer."""
    check(SIGNUPS, request, "Too many sign-ups from this device; try later.")
    code = await service.sign_up(session, slug, payload)
    return JoinDone(message=THANKS, withdraw_code=code)
