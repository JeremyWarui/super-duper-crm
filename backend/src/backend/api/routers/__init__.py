"""One router per resource, all mounted under /api."""

from fastapi import APIRouter

from backend.api.routers import auth

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)

__all__ = ["api_router"]
