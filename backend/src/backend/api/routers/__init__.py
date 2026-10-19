"""One router per resource, all mounted under /api."""

from fastapi import APIRouter

from backend.api.routers import (
    admin,
    auth,
    campaigns,
    events,
    geography,
    mobilizers,
    payments,
    strategy,
    supporters,
    targets,
    users,
)

api_router = APIRouter(prefix="/api")
for module in (
    auth,
    admin,
    geography,
    campaigns,
    targets,
    mobilizers,
    events,
    payments,
    supporters,
    strategy,
    users,
):
    api_router.include_router(module.router)

__all__ = ["api_router"]
