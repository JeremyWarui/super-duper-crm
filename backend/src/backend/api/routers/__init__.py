"""One router per resource, all mounted under /api."""

from fastapi import APIRouter

from backend.api.routers import (
    account,
    admin,
    aspirant_site,
    auth,
    campaigns,
    candidates,
    events,
    files,
    geography,
    join,
    mobilizers,
    party,
    party_aspirants,
    party_console,
    party_members,
    party_volunteers,
    party_workspace,
    payments,
    site,
    strategy,
    supporters,
    targets,
    team,
    users,
    workspace_site,
)

api_router = APIRouter(prefix="/api")
for module in (
    auth,
    account,
    admin,
    join,
    geography,
    files,
    campaigns,
    candidates,
    targets,
    mobilizers,
    site,
    party_workspace,
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
    workspace_site,
    aspirant_site,
):
    api_router.include_router(module.router)
for module in (admin, candidates, party):
    api_router.include_router(module.party_router)

__all__ = ["api_router"]
