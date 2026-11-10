"""The volunteer register for membership officers: list, update, CSV export."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from backend.api.csv_export import cell, csv_response
from backend.api.deps import MembershipOfficer, SessionDep
from backend.api.install import PartyOnlyRoute
from backend.models import VolunteerArea, VolunteerProfile, VolunteerStatus
from backend.schemas.common import PlainQuery
from backend.schemas.volunteers import VolunteerPage, VolunteerRead, VolunteerUpdate
from backend.services import privacy, volunteers
from backend.services.audit import record
from backend.services.volunteers import VolunteerFilters

router = APIRouter(prefix="/party/volunteers", tags=["party"], route_class=PartyOnlyRoute)

CSV_COLUMNS = (
    "full_name",
    "phone",
    "status",
    "interests",
    "interest_other",
    "profession",
    "preferred_contact",
    "polling_station",
    "ward",
    "constituency",
    "county",
    "member_status",
    "created_at",
)


def _filters(
    q: PlainQuery = None,
    status: VolunteerStatus | None = None,
    area: VolunteerArea | None = None,
    county: uuid.UUID | None = None,
    constituency: uuid.UUID | None = None,
    ward: uuid.UUID | None = None,
) -> VolunteerFilters:
    return VolunteerFilters(
        q=q,
        status=status,
        area=area,
        county=county,
        constituency=constituency,
        ward=ward,
    )


FiltersDep = Annotated[VolunteerFilters, Depends(_filters)]


def _read(row: VolunteerProfile) -> VolunteerRead:
    member = row.member
    ward = member.ward
    return VolunteerRead(
        id=row.id,
        member_id=row.member_id,
        full_name=member.full_name,
        phone=member.phone,
        ward=ward,
        constituency=ward.constituency,
        county=ward.constituency.county,
        registration_centre=row.registration_centre,
        profession=row.profession,
        profession_other=row.profession_other,
        status=row.status,
        interests=row.interests,
        interest_other=row.interest_other,
        preferred_contact=row.preferred_contact,
        availability_notes=row.availability_notes,
        member_status=member.status,
        created_at=row.created_at,
        erased_at=row.erased_at,
    )


@router.get("/", response_model=VolunteerPage)
async def list_volunteers(
    user: MembershipOfficer,
    session: SessionDep,
    filters: FiltersDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> VolunteerPage:
    """A page of volunteers, newest first."""
    total, rows = await volunteers.volunteers(session, filters, limit, offset)
    return VolunteerPage(total=total, items=[_read(row) for row in rows])


@router.get("/export.csv")
async def export_volunteers(
    user: MembershipOfficer, session: SessionDep, filters: FiltersDep
) -> Response:
    """Every matching volunteer as CSV; the export is audited before it is sent."""
    rows = await volunteers.export_rows(session, filters)
    record(
        session,
        actor=user,
        action="volunteer.export",
        subject_type="volunteer_profile",
        detail={"filters": filters.given(), "rows": len(rows)},
    )
    await session.commit()
    return csv_response("party-volunteers.csv", CSV_COLUMNS, (_csv_row(row) for row in rows))


def _csv_row(row: VolunteerProfile) -> list[str]:
    member = row.member
    ward = member.ward
    return [
        cell(member.full_name),
        member.phone,
        row.status.value,
        cell(";".join(row.interests)),
        cell(row.interest_other),
        cell(row.profession_other or (row.profession.value if row.profession else "")),
        row.preferred_contact.value,
        cell(row.registration_centre.name if row.registration_centre else ""),
        cell(ward.name),
        cell(ward.constituency.name),
        cell(ward.constituency.county.name),
        member.status.value,
        row.created_at.isoformat(),
    ]


@router.patch("/{volunteer_id}/", response_model=VolunteerRead)
async def update_volunteer(
    volunteer_id: uuid.UUID, payload: VolunteerUpdate, user: MembershipOfficer, session: SessionDep
) -> VolunteerRead:
    """Make a volunteer active or inactive and edit their availability notes."""
    profile = await volunteers.get_volunteer(session, volunteer_id)
    if payload.status is not None:
        await volunteers.set_status(session, profile, VolunteerStatus(payload.status), actor=user)
    if "availability_notes" in payload.model_fields_set:
        volunteers.set_notes(session, profile, payload.availability_notes, actor=user)
    await session.commit()
    return _read(await volunteers.get_volunteer(session, volunteer_id))


@router.post("/{volunteer_id}/erase/", response_model=VolunteerRead)
async def erase_volunteer(
    volunteer_id: uuid.UUID, user: MembershipOfficer, session: SessionDep
) -> VolunteerRead:
    """Blank a withdrawn volunteer profile; the membership is left as it is."""
    profile = await volunteers.get_volunteer(session, volunteer_id)
    await privacy.erase_volunteer(session, profile, actor=user)
    await session.commit()
    return _read(await volunteers.get_volunteer(session, volunteer_id))
