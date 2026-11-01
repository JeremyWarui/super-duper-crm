"""A campaign's own subscription, readable while the campaign is locked."""

from fastapi import APIRouter

from backend.api.deps import SessionDep, SignedInUser, Today
from backend.schemas.billing import OwnSubscription
from backend.services import billing

router = APIRouter(tags=["subscription"])


@router.get("/subscription/", response_model=OwnSubscription)
async def read_own_subscription(
    user: SignedInUser, session: SessionDep, today: Today
) -> OwnSubscription:
    """The state, dates and how to pay; the plan and price only for the candidate and manager."""
    return await billing.own(session, user, today)
