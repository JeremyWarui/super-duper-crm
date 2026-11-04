"""Every request's today is the date in Nairobi."""

from datetime import UTC, date, datetime

import pytest

from backend.api.deps import get_today
from backend.services import clock


class _LateEveningUtc(datetime):
    """22:30 UTC on 1 Nov 2026, already 2 Nov in Nairobi."""

    @classmethod
    def now(cls, tz=None):
        instant = datetime(2026, 11, 1, 22, 30, tzinfo=UTC)
        return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)


async def test_today_is_the_date_in_nairobi_for_every_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(clock, "datetime", _LateEveningUtc)

    assert clock.today() == date(2026, 11, 2)
    assert await get_today() == date(2026, 11, 2)
