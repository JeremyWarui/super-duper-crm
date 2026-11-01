"""One router per resource, all mounted under /api."""

from fastapi import APIRouter

from backend.api.routers import (
    admin,
    auth,
    campaigns,
    events,
    geography,
    join,
    mobilizers,
    party,
    party_aspirants,
    party_finance,
    party_members,
    party_volunteers,
    payments,
    strategy,
    subscription,
    supporters,
    targets,
    team,
    users,
)

api_router = APIRouter(prefix="/api")
for module in (
    auth,
    admin,
    join,
    geography,
    campaigns,
    targets,
    mobilizers,
    party,
    party_aspirants,
    party_finance,
    party_members,
    party_volunteers,
    events,
    payments,
    supporters,
    strategy,
    subscription,
    team,
    users,
):
    api_router.include_router(module.router)

__all__ = ["api_router"]
