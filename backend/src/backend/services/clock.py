"""Today's date in Nairobi, and stored times read back in UTC."""

from datetime import UTC, date, datetime, timedelta, timezone

# Kenya keeps UTC+3 all year.
NAIROBI = timezone(timedelta(hours=3))


def today() -> date:
    return datetime.now(NAIROBI).date()


def as_utc(moment: datetime) -> datetime:
    """A stored time with its zone; SQLite hands them back without one, and they are UTC."""
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)
