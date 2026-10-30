"""Read and replace the party's settings row."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import PartySettings, User
from backend.schemas.party import PartySettingsUpdate
from backend.services.audit import record
from backend.services.errors import NotFound


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
    row = await read_settings(session)
    values = payload.model_dump()
    changed = sorted(name for name, value in values.items() if getattr(row, name) != value)
    for name, value in values.items():
        setattr(row, name, value)
    row.updated_at = datetime.now(UTC)
    record(
        session,
        actor=actor,
        action="party_settings.update",
        subject_type="party_settings",
        detail={"fields": changed},
    )
    await session.commit()
    return row
