"""News sign-ups from the website footer, and undoing them by their code."""

import secrets

from sqlalchemy import delete
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Subscriber
from backend.services.consent import SUBSCRIBE_WORDING
from backend.services.party import read_settings


async def subscribe(session: AsyncSession, contact: str, channel: str) -> str:
    """Record a sign-up and return its unsubscribe code.

    A contact already signed up keeps its first row and code, and the same single insert runs
    either way, so the answer does not show whether the contact was known.
    """
    settings = await read_settings(session)
    code = secrets.token_urlsafe(18)
    dialect = postgresql if session.bind.dialect.name == "postgresql" else sqlite
    await session.execute(
        dialect.insert(Subscriber)
        .values(
            contact=contact,
            channel=channel,
            consent_wording=SUBSCRIBE_WORDING,
            notice_version=settings.privacy_notice_version,
            unsubscribe_code=code,
        )
        .on_conflict_do_nothing()
    )
    return code


async def unsubscribe(session: AsyncSession, code: str) -> None:
    """Delete the sign-up with this code, if there is one."""
    await session.execute(delete(Subscriber).where(Subscriber.unsubscribe_code == code))
