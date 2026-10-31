"""The party register for membership officers: list, detail, status moves, CSV export."""

import csv
import io
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from backend.api.deps import MembershipOfficer, SessionDep
from backend.models import PartyMember, PartyMemberStatus
from backend.schemas.common import plain_text
from backend.schemas.party import MemberDetail, MemberMove, MemberPage, MemberRead
from backend.services import membership
from backend.services.audit import record
from backend.services.membership import MemberFilters

router = APIRouter(prefix="/party/members", tags=["party"])

CSV_COLUMNS = (
    "full_name",
    "phone",
    "email",
    "status",
    "ward",
    "constituency",
    "county",
    "created_at",
)


def _filters(
    q: str | None = None,
    status: PartyMemberStatus | None = None,
    county: uuid.UUID | None = None,
    constituency: uuid.UUID | None = None,
    ward: uuid.UUID | None = None,
) -> MemberFilters:
    try:
        plain_text(q)
    except ValueError as refused:
        raise HTTPException(status_code=400, detail=str(refused)) from None
    return MemberFilters(q=q, status=status, county=county, constituency=constituency, ward=ward)


FiltersDep = Annotated[MemberFilters, Depends(_filters)]


FORMULA_LEADS = ("=", "+", "-", "@", chr(9), chr(13))


def _cell(text: str) -> str:
    """Text a spreadsheet will not run as a formula."""
    return "'" + text if text[:1] in FORMULA_LEADS else text


def _place(row: PartyMember) -> dict:
    ward = row.ward
    return {
        "ward": ward,
        "constituency": ward.constituency,
        "county": ward.constituency.county,
    }


def _read(row: PartyMember, model: type[MemberRead]) -> MemberRead:
    values = {name: getattr(row, name) for name in model.model_fields if name not in _PLACES}
    return model(**values, **_place(row))


_PLACES = ("ward", "constituency", "county")


@router.get("/", response_model=MemberPage)
async def list_members(
    user: MembershipOfficer,
    session: SessionDep,
    filters: FiltersDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> MemberPage:
    """A page of the register, newest first."""
    total, rows = await membership.members(session, filters, limit, offset)
    return MemberPage(total=total, items=[_read(row, MemberRead) for row in rows])


@router.get("/export.csv")
async def export_members(
    user: MembershipOfficer, session: SessionDep, filters: FiltersDep
) -> Response:
    """Every matching member as CSV; the export is audited before it is sent."""
    rows = await membership.export_rows(session, filters)
    record(
        session,
        actor=user,
        action="member.export",
        subject_type="party_member",
        detail={"filters": filters.given(), "rows": len(rows)},
    )
    await session.commit()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(CSV_COLUMNS)
    for row in rows:
        ward = row.ward
        writer.writerow(
            [
                _cell(row.full_name),
                row.phone,
                _cell(row.email or ""),
                row.status.value,
                ward.name,
                ward.constituency.name,
                ward.constituency.county.name,
                row.created_at.isoformat(),
            ]
        )
    return Response(
        out.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="party-members.csv"'},
    )


@router.get("/{member_id}/", response_model=MemberDetail)
async def get_member(member_id: uuid.UUID, user: MembershipOfficer, session: SessionDep):
    member = await membership.get_member(session, member_id)
    return _read(member, MemberDetail)


@router.post("/{member_id}/status/", response_model=MemberDetail)
async def move_member(
    member_id: uuid.UUID, payload: MemberMove, user: MembershipOfficer, session: SessionDep
):
    """Move a member to a new status, with an optional reason."""
    member = await membership.get_member(session, member_id)
    await membership.move(session, member, payload.status, actor=user, reason=payload.reason)
    await session.commit()
    return _read(await membership.get_member(session, member_id), MemberDetail)
