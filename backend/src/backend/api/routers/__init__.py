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
    party_finance,
    party_members,
    party_payouts,
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
    account,
    admin,
    join,
    geography,
    campaigns,
    candidates,
    targets,
    mobilizers,
    party,
    party_aspirants,
    party_finance,
    party_members,
    party_payouts,
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
