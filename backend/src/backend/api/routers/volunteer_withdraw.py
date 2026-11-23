"""Leaving the campaign's volunteer list by the code its sign-up gave."""

from fastapi import APIRouter, Request

from backend.api.deps import SessionDep
from backend.api.limits import check
from backend.schemas.join import Withdrawn
from backend.services import campaign_volunteers
from backend.services.ratelimit import RateLimit

router = APIRouter(prefix="/website", tags=["website"])

WITHDRAWALS = RateLimit(limit=20, window=3600)
# The same answer for every code, so a code cannot be tested for whether it was real.
WITHDRAWN = "Done. If you were on this campaign's volunteer list, you are off it now."


@router.post("/volunteer/withdraw/{code}/", response_model=Withdrawn)
async def withdraw(code: str, request: Request, session: SessionDep) -> Withdrawn:
    """Take a volunteer off the campaign's list; the answer is the same for any code."""
    check(WITHDRAWALS, request)
    await campaign_volunteers.withdraw(session, code)
    return Withdrawn(message=WITHDRAWN)
