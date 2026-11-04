"""The website's candidates: the directory, each profile, and its "Support" volunteer form."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status

from backend.api.deps import SessionDep, Today
from backend.api.routers.join import _client
from backend.models import Seat
from backend.schemas.candidates import CandidateCard, CandidateDetail, CandidateVolunteerCreate
from backend.schemas.join import JoinDone, Withdrawn
from backend.services import candidates as service
from backend.services.ratelimit import RateLimit

router = APIRouter(prefix="/candidates", tags=["candidates"])

SIGNUPS = RateLimit(limit=20, window=3600)
WITHDRAWALS = RateLimit(limit=20, window=3600)
THANKS = "Thank you. The campaign team will contact you."
# The same answer for every code, so a code cannot be tested for whether it was real.
WITHDRAWN = "Done. If you were on this campaign's volunteer list, you are off it now."


@router.get("/", response_model=list[CandidateCard])
async def list_candidates(
    session: SessionDep,
    seat: Seat | None = None,
    county: uuid.UUID | None = None,
    q: Annotated[str, Query(max_length=100)] = "",
) -> list[CandidateCard]:
    """Approved aspirants whose profile the party has published."""
    return await service.candidates(session, seat=seat.value if seat else None, county=county, q=q)


@router.post("/volunteer/withdraw/{code}/", response_model=Withdrawn)
async def withdraw(code: str, request: Request, session: SessionDep) -> Withdrawn:
    """Take a volunteer off a campaign's list; the answer is the same for any code."""
    if not WITHDRAWALS.allow(_client(request)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many tries; try later.")
    await service.withdraw(session, code)
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
    today: Today,
) -> JoinDone:
    """Sign up to volunteer for the candidate's campaign; a known phone gets the same answer."""
    if not SIGNUPS.allow(_client(request)):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many sign-ups from this device; try later."
        )
    code = await service.sign_up(session, slug, payload, today)
    return JoinDone(message=THANKS, withdraw_code=code)
