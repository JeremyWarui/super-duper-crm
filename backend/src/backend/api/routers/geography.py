"""Reference geography: counties, constituencies, wards and registration centres.

Read-only. The rows are loaded once by the seeder, not created through the API.
A mobilizer sees only their own ward and the centres inside it.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import selectinload

from backend.api.deps import CurrentUser, SessionDep, get_current_user, mobilizer_ward_id
from backend.models import Constituency, County, RegistrationCentre, Ward
from backend.schemas.geography import (
    ConstituencyRead,
    CountyRead,
    RegistrationCentreRead,
    WardRead,
)

router = APIRouter(tags=["geography"], dependencies=[Depends(get_current_user)])


async def _all(session: SessionDep, statement: Select) -> list:
    return list((await session.execute(statement)).scalars().all())


@router.get("/counties/", response_model=list[CountyRead])
async def list_counties(session: SessionDep) -> list[County]:
    return await _all(session, select(County).order_by(County.name))


@router.get("/counties/{county_id}/", response_model=CountyRead)
async def get_county(county_id: uuid.UUID, session: SessionDep) -> County:
    county = await session.get(County, county_id)
    if county is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such county.")
    return county


@router.get("/constituencies/", response_model=list[ConstituencyRead])
async def list_constituencies(
    session: SessionDep, county: uuid.UUID | None = None
) -> list[Constituency]:
    statement = (
        select(Constituency).options(selectinload(Constituency.county)).order_by(Constituency.name)
    )
    if county is not None:
        statement = statement.where(Constituency.county_id == county)
    return await _all(session, statement)


@router.get("/wards/", response_model=list[WardRead])
async def list_wards(
    session: SessionDep, user: CurrentUser, constituency: uuid.UUID | None = None
) -> list[Ward]:
    statement = select(Ward).options(selectinload(Ward.constituency)).order_by(Ward.name)
    if constituency is not None:
        statement = statement.where(Ward.constituency_id == constituency)
    own_ward = mobilizer_ward_id(user)
    if own_ward is not None:
        statement = statement.where(Ward.id == own_ward)
    return await _all(session, statement)


@router.get("/centres/", response_model=list[RegistrationCentreRead])
async def list_centres(
    session: SessionDep, user: CurrentUser, ward: uuid.UUID | None = None
) -> list[RegistrationCentre]:
    statement = (
        select(RegistrationCentre)
        .options(selectinload(RegistrationCentre.ward))
        .order_by(RegistrationCentre.name)
    )
    if ward is not None:
        statement = statement.where(RegistrationCentre.ward_id == ward)
    own_ward = mobilizer_ward_id(user)
    if own_ward is not None:
        statement = statement.where(RegistrationCentre.ward_id == own_ward)
    return await _all(session, statement)
