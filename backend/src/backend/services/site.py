"""Read and replace the site settings row; the organisation type is read-only here."""

from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import replace_fields
from backend.models import OrganisationType, SiteSettings, User
from backend.schemas.site import SiteSettingsUpdate
from backend.services.audit import record
from backend.services.errors import NotFound

_organisation_type: OrganisationType | None = None


async def read_settings(session: AsyncSession) -> SiteSettings:
    """The one site settings row."""
    row = await session.get(SiteSettings, 1)
    if row is None:
        raise NotFound("The site settings row is missing.")
    return row


async def organisation_type(session: AsyncSession) -> OrganisationType:
    """Party or aspirant; read once per process, since setup fixes it for good."""
    global _organisation_type
    if _organisation_type is None:
        value = await session.scalar(
            select(SiteSettings.organisation_type).where(SiteSettings.id == 1)
        )
        if value is None:
            raise NotFound("The site settings row is missing.")
        _organisation_type = value
    return _organisation_type


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
