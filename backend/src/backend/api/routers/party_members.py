"""The party register for membership officers: list, detail, status moves, CSV export."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from backend.api.csv_export import cell, csv_response
from backend.api.deps import MembershipOfficer, SessionDep
from backend.api.install import PartyOnlyRoute
from backend.models import PartyMember, PartyMemberStatus
from backend.schemas.common import PlainQuery
from backend.schemas.party import MemberDetail, MemberMove, MemberPage, MemberRead
from backend.services import membership, privacy
from backend.services.audit import record
from backend.services.membership import MemberFilters

router = APIRouter(prefix="/party/members", tags=["party"], route_class=PartyOnlyRoute)

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
    q: PlainQuery = None,
    status: PartyMemberStatus | None = None,
    county: uuid.UUID | None = None,
    constituency: uuid.UUID | None = None,
    ward: uuid.UUID | None = None,
) -> MemberFilters:
    return MemberFilters(q=q, status=status, county=county, constituency=constituency, ward=ward)


FiltersDep = Annotated[MemberFilters, Depends(_filters)]


def _place(row: PartyMember) -> dict:
    ward = row.ward
    return {
        "ward": ward,
        "constituency": ward.constituency,
        "county": ward.constituency.county,
    }


def _read(row: PartyMember, model: type[MemberRead], logins: set[uuid.UUID]) -> MemberRead:
    values = {name: getattr(row, name) for name in model.model_fields if name not in _COMPUTED}
    return model(**values, **_place(row), has_login=row.id in logins)


_COMPUTED = ("ward", "constituency", "county", "has_login")


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
    logins = await membership.with_logins(session, [row.id for row in rows])
    return MemberPage(total=total, items=[_read(row, MemberRead, logins) for row in rows])


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
    return csv_response(
        "party-members.csv",
        CSV_COLUMNS,
        (
            [
                cell(row.full_name),
                row.phone,
                cell(row.email or ""),
                row.status.value,
                row.ward.name,
                row.ward.constituency.name,
                row.ward.constituency.county.name,
                row.created_at.isoformat(),
            ]
            for row in rows
        ),
    )


async def _detail(session: SessionDep, member_id: uuid.UUID) -> MemberDetail:
    member = await membership.get_member(session, member_id)
    return _read(member, MemberDetail, await membership.with_logins(session, [member.id]))


@router.get("/{member_id}/", response_model=MemberDetail)
async def get_member(member_id: uuid.UUID, user: MembershipOfficer, session: SessionDep):
    return await _detail(session, member_id)


@router.post("/{member_id}/status/", response_model=MemberDetail)
async def move_member(
    member_id: uuid.UUID, payload: MemberMove, user: MembershipOfficer, session: SessionDep
):
    """Move a member to a new status, with an optional reason."""
    member = await membership.get_member(session, member_id)
    await membership.move(session, member, payload.status, actor=user, reason=payload.reason)
    await session.commit()
    return await _detail(session, member_id)


@router.post("/{member_id}/erase/", response_model=MemberDetail)
async def erase_member(member_id: uuid.UUID, user: MembershipOfficer, session: SessionDep):
    """Blank a withdrawn or rejected member's personal details on their request."""
    member = await membership.get_member(session, member_id)
    await privacy.erase_member(session, member, actor=user)
    await session.commit()
    return await _detail(session, member_id)
