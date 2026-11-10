"""Read and replace the party-only settings row."""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import PartySettings, User
from backend.schemas.party import PartySettingsUpdate
from backend.services.errors import NotFound
from backend.services.site import replace_settings


async def read_settings(session: AsyncSession) -> PartySettings:
    """The one settings row, which the migration creates."""
    row = await session.get(PartySettings, 1)
    if row is None:
        raise NotFound("The party settings row is missing.")
    return row


async def update_settings(
    session: AsyncSession, payload: PartySettingsUpdate, *, actor: User | None
) -> PartySettings:
    """Replace every editable field and audit the names of those that changed."""
    return await replace_settings(
        session, await read_settings(session), payload, "party_settings", actor=actor
    )
