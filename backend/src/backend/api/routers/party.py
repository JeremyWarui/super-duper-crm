"""The party's public identity, readable without a login."""

from fastapi import APIRouter

from backend.api.deps import SessionDep
from backend.schemas.party import PartySettingsRead
from backend.services import party as service

router = APIRouter(prefix="/party", tags=["party"])


@router.get("/", response_model=PartySettingsRead)
async def get_party(session: SessionDep) -> PartySettingsRead:
    return await service.read_settings(session)
