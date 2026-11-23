"""Read and replace the site settings row."""

from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import replace_fields
from backend.models import SiteSettings, User
from backend.schemas.site import SiteSettingsUpdate
from backend.services.audit import record
from backend.services.errors import NotFound

_set_up = False


async def read_settings(session: AsyncSession) -> SiteSettings:
    """The one site settings row."""
    row = await session.get(SiteSettings, 1)
    if row is None:
        raise NotFound("The site settings row is missing.")
    return row


async def is_set_up(session: AsyncSession) -> bool:
    """Whether setup has written the site settings row; once true, never read again."""
    global _set_up
    if not _set_up:
        _set_up = (
            await session.scalar(select(SiteSettings.id).where(SiteSettings.id == 1)) is not None
        )
    return _set_up


async def update_settings(
    session: AsyncSession, payload: SiteSettingsUpdate, *, actor: User | None
) -> SiteSettings:
    """Replace every editable field and audit the names of those that changed."""
    return await replace_settings(
        session, await read_settings(session), payload, "site_settings", actor=actor
    )


async def replace_settings[Row](
    session: AsyncSession, row: Row, payload: BaseModel, kind: str, *, actor: User | None
) -> Row:
    """Replace a settings row's editable fields and audit `<kind>.update` with the changed names."""
    changed = replace_fields(row, payload.model_dump())
    row.updated_at = datetime.now(UTC)
    record(
        session,
        actor=actor,
        action=f"{kind}.update",
        subject_type=kind,
        detail={"fields": changed},
    )
    await session.commit()
    return row
