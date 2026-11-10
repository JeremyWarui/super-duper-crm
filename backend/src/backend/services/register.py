"""Search, place filters and paging shared by the party's member and volunteer registers."""

import enum
import uuid
from dataclasses import dataclass, fields

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Constituency, PartyMember, Ward


@dataclass(frozen=True)
class PlaceFilters:
    """A name-or-phone search and the county, constituency and ward a register is narrowed to."""

    q: str | None = None
    county: uuid.UUID | None = None
    constituency: uuid.UUID | None = None
    ward: uuid.UUID | None = None

    def given(self) -> dict[str, str | bool]:
        """The filters in use, for the audit trail; `q` is recorded only as set."""
        found: dict[str, str | bool] = {}
        for field in fields(self):
            value = getattr(self, field.name)
            if field.name == "q":
                if value:
                    found["q"] = True
            elif value is not None:
                found[field.name] = value.value if isinstance(value, enum.Enum) else str(value)
        return found


def person_matches(q: str | None) -> ColumnElement[bool] | None:
    """Members whose name or phone contains `q`; None when `q` is blank.

    Phones are stored as +254..., so a number typed as 07... finds them too.
    """
    text = (q or "").strip()
    if not text:
        return None
    matches = PartyMember.full_name.icontains(text, autoescape=True) | PartyMember.phone.contains(
        text, autoescape=True
    )
    local = (q or "").replace(" ", "")
    if local.startswith("0") and local[1:].isdigit():
        matches |= PartyMember.phone.contains("+254" + local[1:], autoescape=True)
    return matches


def in_place(statement: Select, filters: PlaceFilters) -> Select:
    """Narrow a statement joined to the member's ward and constituency to the filters' places."""
    matches = person_matches(filters.q)
    if matches is not None:
        statement = statement.where(matches)
    if filters.county is not None:
        statement = statement.where(Constituency.county_id == filters.county)
    if filters.constituency is not None:
        statement = statement.where(Ward.constituency_id == filters.constituency)
    if filters.ward is not None:
        statement = statement.where(PartyMember.ward_id == filters.ward)
    return statement


async def page(
    session: AsyncSession, statement: Select, id_column, limit: int, offset: int
) -> tuple[int, list]:
    """One page of `statement` and the count of every row it matches."""
    total = await session.scalar(
        select(func.count()).select_from(
            statement.order_by(None).with_only_columns(id_column).subquery()
        )
    )
    rows = await session.scalars(statement.limit(limit).offset(offset))
    return total or 0, list(rows.unique())
