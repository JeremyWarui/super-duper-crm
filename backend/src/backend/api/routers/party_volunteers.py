"""The volunteer register for membership officers: list, update, CSV export."""

import csv
import io
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from backend.api.deps import MembershipOfficer, SessionDep
from backend.models import VolunteerInterest, VolunteerProfile, VolunteerStatus
from backend.schemas.common import plain_text
from backend.schemas.volunteers import VolunteerPage, VolunteerRead, VolunteerUpdate
from backend.services import membership, volunteers
from backend.services.audit import record
from backend.services.volunteers import VolunteerFilters

router = APIRouter(prefix="/party/volunteers", tags=["party"])

CSV_COLUMNS = (
    "full_name",
    "phone",
    "status",
    "interests",
    "preferred_contact",
    "ward",
    "constituency",
    "county",
    "member_status",
    "created_at",
)

FORMULA_LEADS = ("=", "+", "-", "@", chr(9), chr(13))


def _filters(
    q: str | None = None,
    status: VolunteerStatus | None = None,
    interest: VolunteerInterest | None = None,
    county: uuid.UUID | None = None,
    constituency: uuid.UUID | None = None,
    ward: uuid.UUID | None = None,
) -> VolunteerFilters:
    try:
        plain_text(q)
    except ValueError as refused:
        raise HTTPException(status_code=400, detail=str(refused)) from None
    return VolunteerFilters(
        q=q,
        status=status,
        interest=interest,
        county=county,
        constituency=constituency,
        ward=ward,
    )


FiltersDep = Annotated[VolunteerFilters, Depends(_filters)]


def _cell(text: str) -> str:
    """Text a spreadsheet will not run as a formula."""
    return "'" + text if text[:1] in FORMULA_LEADS else text


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
        status=row.status,
        interests=row.interests,
        preferred_contact=row.preferred_contact,
        availability_notes=row.availability_notes,
        member_status=member.status,
        created_at=row.created_at,
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
    await membership.process_requests(session)
    total, rows = await volunteers.volunteers(session, filters, limit, offset)
    return VolunteerPage(total=total, items=[_read(row) for row in rows])


@router.get("/export.csv")
async def export_volunteers(
    user: MembershipOfficer, session: SessionDep, filters: FiltersDep
) -> Response:
    """Every matching volunteer as CSV; the export is audited before it is sent."""
    await membership.process_requests(session)
    rows = await volunteers.export_rows(session, filters)
    record(
        session,
        actor=user,
        action="volunteer.export",
        subject_type="volunteer_profile",
        detail={"filters": filters.given(), "rows": len(rows)},
    )
    await session.commit()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(CSV_COLUMNS)
    for row in rows:
        member = row.member
        ward = member.ward
        writer.writerow(
            [
                _cell(member.full_name),
                member.phone,
                row.status.value,
                _cell(";".join(row.interests)),
                row.preferred_contact.value,
                _cell(ward.name),
                _cell(ward.constituency.name),
                _cell(ward.constituency.county.name),
                member.status.value,
                row.created_at.isoformat(),
            ]
        )
    return Response(
        out.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="party-volunteers.csv"'},
    )


@router.patch("/{volunteer_id}/", response_model=VolunteerRead)
async def update_volunteer(
    volunteer_id: uuid.UUID, payload: VolunteerUpdate, user: MembershipOfficer, session: SessionDep
) -> VolunteerRead:
    """Make a volunteer active or inactive and edit their availability notes."""
    await membership.process_requests(session)
    profile = await volunteers.get_volunteer(session, volunteer_id)
    if payload.status is not None:
        await volunteers.set_status(session, profile, VolunteerStatus(payload.status), actor=user)
    if "availability_notes" in payload.model_fields_set:
        volunteers.set_notes(session, profile, payload.availability_notes, actor=user)
    await session.commit()
    return _read(await volunteers.get_volunteer(session, volunteer_id))
