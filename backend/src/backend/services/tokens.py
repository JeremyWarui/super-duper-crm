"""One-time secrets kept only as their SHA-256: whether one is live, and spending it once."""

from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.clock import as_utc


def is_live(expires_at: datetime | None, used_at: datetime | None = None) -> bool:
    """Not used, and not yet expired; a missing expiry counts as expired."""
    return used_at is None and expires_at is not None and as_utc(expires_at) > datetime.now(UTC)


async def spend(session: AsyncSession, model: type, match, *still, **values) -> bool:
    """Write `values` to the one row of `model` matching `match` and `still`; False when another
    request spent it first, so two requests racing on one secret cannot both get through."""
    spent = await session.execute(update(model).where(match, *still).values(**values))
    return spent.rowcount == 1
