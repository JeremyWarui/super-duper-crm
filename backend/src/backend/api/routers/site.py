"""The website's settings and organisation type, public to read."""

from fastapi import APIRouter

from backend.api.deps import SessionDep
from backend.schemas.site import SiteSettingsRead
from backend.services import site as service

router = APIRouter(prefix="/site", tags=["site"])


@router.get("/", response_model=SiteSettingsRead)
async def get_site(session: SessionDep) -> SiteSettingsRead:
    return await service.read_settings(session)
