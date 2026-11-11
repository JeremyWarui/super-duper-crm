"""Reference geography, read-only; a mobilizer sees only their own ward."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import selectinload

from backend.api.deps import CurrentUser, SessionDep, get_current_user
from backend.api.scope import all_rows, mobilizer_ward_id
from backend.db.session import get_or_refuse
from backend.models import Constituency, County, RegistrationCentre, Ward
from backend.schemas.geography import (
    ConstituencyRead,
    CountyRead,
    RegistrationCentreRead,
    WardRead,
)
from backend.services.geography import in_level, places

router = APIRouter(tags=["geography"], dependencies=[Depends(get_current_user)])


@router.get("/counties/", response_model=list[CountyRead])
async def list_counties(session: SessionDep) -> list[County]:
    return await places(session, County)


@router.get("/counties/{county_id}/", response_model=CountyRead)
async def get_county(county_id: uuid.UUID, session: SessionDep) -> County:
    return await get_or_refuse(session, County, county_id, "county")


@router.get("/constituencies/", response_model=list[ConstituencyRead])
async def list_constituencies(
    session: SessionDep, county: uuid.UUID | None = None
) -> list[Constituency]:
    return await all_rows(
        session, in_level(Constituency, county).options(selectinload(Constituency.county))
    )


@router.get("/wards/", response_model=list[WardRead])
async def list_wards(
    session: SessionDep,
    user: CurrentUser,
    constituency: uuid.UUID | None = None,
    county: uuid.UUID | None = None,
) -> list[Ward]:
    """Every ward, or those in one constituency or county."""
    statement = in_level(Ward, constituency).options(selectinload(Ward.constituency))
    if county is not None:
        statement = statement.join(Constituency).where(Constituency.county_id == county)
    own_ward = mobilizer_ward_id(user)
    if own_ward is not None:
        statement = statement.where(Ward.id == own_ward)
    return await all_rows(session, statement)


@router.get("/centres/", response_model=list[RegistrationCentreRead])
async def list_centres(
    session: SessionDep, user: CurrentUser, ward: uuid.UUID | None = None
) -> list[RegistrationCentre]:
    statement = in_level(RegistrationCentre, ward).options(selectinload(RegistrationCentre.ward))
    own_ward = mobilizer_ward_id(user)
    if own_ward is not None:
        statement = statement.where(RegistrationCentre.ward_id == own_ward)
    return await all_rows(session, statement)
