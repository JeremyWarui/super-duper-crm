"""One router per resource, all mounted under /api."""

from fastapi import APIRouter

from backend.api.routers import (
    account,
    admin,
    agents,
    aspirant_site,
    assignments,
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
    setup,
    site,
    strategy,
    supporters,
    targets,
    team,
    team_signup,
    users,
    workspace_site,
)

api_router = APIRouter(prefix="/api")
for module in (
    setup,
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
    team_signup,
    agents,
    assignments,
    users,
    workspace_site,
    aspirant_site,
):
    api_router.include_router(module.router)
for module in (admin, candidates, party):
    api_router.include_router(module.party_router)

__all__ = ["api_router"]
