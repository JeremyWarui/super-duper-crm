"""One router per resource, all mounted under /api."""

from fastapi import APIRouter

from backend.api.routers import (
    account,
    admin,
    auth,
    campaigns,
    candidates,
    events,
    geography,
    join,
    mobilizers,
    party,
    party_aspirants,
    party_console,
    party_members,
    party_volunteers,
    payments,
    site,
    strategy,
    supporters,
    targets,
    team,
    users,
)

api_router = APIRouter(prefix="/api")
for module in (
    auth,
    account,
    admin,
    join,
    geography,
    campaigns,
    candidates,
    targets,
    mobilizers,
    site,
    party,
    party_aspirants,
    party_console,
    party_members,
    party_volunteers,
    events,
    payments,
    supporters,
    strategy,
    team,
    users,
):
    api_router.include_router(module.router)
for module in (admin, candidates, party):
    api_router.include_router(module.party_router)

__all__ = ["api_router"]
