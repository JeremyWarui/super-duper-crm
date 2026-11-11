"""The places of one level, as every picker and listing reads them."""

import uuid

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Constituency, County, RegistrationCentre, Ward

Place = County | Constituency | Ward | RegistrationCentre

# The column naming each level's parent; a county has none.
PARENT = {
    County: None,
    Constituency: Constituency.county_id,
    Ward: Ward.constituency_id,
    RegistrationCentre: RegistrationCentre.ward_id,
}


def in_level(model: type[Place], parent: uuid.UUID | None = None) -> Select:
    """The level's places still in use, by name, only those under `parent` when given."""
    statement = select(model).where(model.retired.is_(False)).order_by(model.name)
    if parent is not None:
        statement = statement.where(PARENT[model] == parent)
    return statement


async def places(
    session: AsyncSession, model: type[Place], parent: uuid.UUID | None = None
) -> list[Place]:
    return list(await session.scalars(in_level(model, parent)))
