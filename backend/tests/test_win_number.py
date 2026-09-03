"""`compute_win_number` - the one piece of real arithmetic in the model layer.

It was broken in the Django version (it read a field that did not exist), so it
gets the table-driven treatment: the boundary where floor() flips, the zero and
None guards, and the odd/even split.
"""

from decimal import Decimal

import pytest

from backend.models import compute_win_number


@pytest.mark.parametrize(
    ("registered_voters", "turnout_pct", "expected"),
    [
        # 10000 * 65% = 6500 cast -> 3250 is half -> 3251 wins.
        (10_000, Decimal("65.00"), 3_251),
        # Odd projected cast: 1001 -> floor(500.5) = 500 -> 501.
        (2_002, Decimal("50.00"), 501),
        # Full turnout of a 3-voter roll: 3 cast -> floor(1.5) = 1 -> 2.
        (3, Decimal("100.00"), 2),
        # Fractional projection floors before halving: 999 * 33.33% = 332.9667.
        (999, Decimal("33.33"), 167),
        # Smallest non-trivial roll.
        (1, Decimal("100.00"), 1),
        # Turnout below the level where a single vote is projected.
        (10, Decimal("1.00"), 1),
    ],
)
def test_win_number_is_half_the_projected_cast_plus_one(
    registered_voters: int, turnout_pct: Decimal, expected: int
) -> None:
    assert compute_win_number(registered_voters, turnout_pct) == expected


@pytest.mark.parametrize(
    ("registered_voters", "turnout_pct"),
    [
        (None, Decimal("65.00")),
        (10_000, None),
        (None, None),
        (0, Decimal("65.00")),
        (10_000, Decimal("0.00")),
    ],
)
def test_win_number_is_none_when_nothing_is_projected_to_be_cast(
    registered_voters: int | None, turnout_pct: Decimal | None
) -> None:
    assert compute_win_number(registered_voters, turnout_pct) is None


def test_win_number_uses_exact_decimal_arithmetic() -> None:
    """The float version of this formula lands on the wrong side of the floor.

    Django computed `registered_voters * float(pct) / 100`. For a 375-voter
    centre at 36.8% turnout that is 137.99999999999997 rather than 138, so the
    floor drops to 68 and the win number comes out one vote short: 69, not 70.
    Under-stating a win number is the expensive direction to be wrong in.
    """
    registered_voters, turnout = 375, Decimal("36.8")

    django_float_result = int((registered_voters * float(turnout) / 100) // 2) + 1
    assert django_float_result == 69, "the float trap, reproduced"

    assert compute_win_number(registered_voters, turnout) == 70
