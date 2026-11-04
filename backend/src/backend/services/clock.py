"""Today's date in Nairobi."""

from datetime import date, datetime, timedelta, timezone

# Kenya keeps UTC+3 all year.
NAIROBI = timezone(timedelta(hours=3))


def today() -> date:
    return datetime.now(NAIROBI).date()
