"""Campaign subscriptions: what one allows on a given day."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from backend.models.enums import AccessState, SubscriptionHold

# Kenya keeps UTC+3 all year.
NAIROBI = timezone(timedelta(hours=3))
GRACE_DAYS = 7
READ_ONLY_DAYS = 7

FULL_ACCESS = frozenset({AccessState.ACTIVE, AccessState.GRACE_PERIOD})
NO_ACCESS = frozenset({AccessState.PENDING_PAYMENT, AccessState.LOCKED, AccessState.CANCELLED})


def today() -> date:
    """Today's date in Nairobi."""
    return datetime.now(NAIROBI).date()


@dataclass(frozen=True)
class Access:
    state: AccessState
    paid_until: date | None
    read_only_from: date | None
    locks_on: date | None


def access(
    paid_until: date | None,
    hold: SubscriptionHold,
    on: date,
    grace_days: int = GRACE_DAYS,
    read_only_days: int = READ_ONLY_DAYS,
) -> Access:
    """The access state on day `on`, from the last paid day (inclusive) and the hold."""
    if paid_until is None:
        read_only_from = locks_on = None
    else:
        read_only_from = paid_until + timedelta(days=grace_days + 1)
        locks_on = read_only_from + timedelta(days=read_only_days)

    if hold is SubscriptionHold.CANCELLED:
        state = AccessState.CANCELLED
    elif hold is SubscriptionHold.SUSPENDED:
        state = AccessState.LOCKED
    elif paid_until is None:
        state = AccessState.PENDING_PAYMENT
    elif on <= paid_until:
        state = AccessState.ACTIVE
    elif on < read_only_from:
        state = AccessState.GRACE_PERIOD
    elif on < locks_on:
        state = AccessState.READ_ONLY
    else:
        state = AccessState.LOCKED
    return Access(state, paid_until, read_only_from, locks_on)
