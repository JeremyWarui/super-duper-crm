"""The party console's top bar: search and notifications, limited to the caller's offices."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from backend.api.deps import CurrentUser, SessionDep
from backend.api.install import PartyOnlyRoute
from backend.models import User
from backend.schemas.common import plain_text
from backend.schemas.console import Notification, SearchHit
from backend.services import console

router = APIRouter(prefix="/party", tags=["party"], route_class=PartyOnlyRoute)


def _staff(user: User) -> None:
    if not console.offices(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This is for party staff.")


@router.get("/search/", response_model=list[SearchHit])
async def search(
    user: CurrentUser,
    session: SessionDep,
    q: Annotated[str, Query(min_length=2, max_length=100)],
) -> list[SearchHit]:
    """Members and aspirants by name or phone, each kind only for the office that opens it."""
    _staff(user)
    try:
        plain_text(q)
    except ValueError as refused:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(refused)) from None
    return await console.search(session, user, q)


@router.get("/notifications/", response_model=list[Notification])
async def notifications(user: CurrentUser, session: SessionDep) -> list[Notification]:
    """What waits on each of the caller's offices, with how many."""
    _staff(user)
    return await console.notifications(session, user)
