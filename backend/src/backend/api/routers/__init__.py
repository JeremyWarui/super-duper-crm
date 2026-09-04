"""One router per resource, all mounted under /api."""

from fastapi import APIRouter

from backend.api.routers import (
    auth,
    campaigns,
    events,
    geography,
    mobilizers,
    strategy,
    supporters,
    targets,
    users,
)

api_router = APIRouter(prefix="/api")
for module in (
    auth,
    geography,
    campaigns,
    targets,
    mobilizers,
    events,
    supporters,
    strategy,
    users,
):
    api_router.include_router(module.router)

__all__ = ["api_router"]
