"""The party office's branch pages: every county's branch, and the terms in each branch office,
kept by the Membership Officer."""

import uuid

from fastapi import APIRouter, UploadFile, status
from fastapi.responses import FileResponse

from backend.api.deps import MembershipOfficer, SessionDep, Today
from backend.api.install import PartyOnlyRoute
from backend.api.uploads import private_file, store_upload
from backend.models import BranchOfficial, FileArea
from backend.schemas.content import (
    CountyBranch,
    MinutesRead,
    OfficialAppoint,
    OfficialEnd,
    OfficialRead,
    OfficialsRead,
)
from backend.services import branch_officials as service
from backend.services import branches as branch_service

router = APIRouter(prefix="/party/office", tags=["party"], route_class=PartyOnlyRoute)


@router.get("/branches/", response_model=list[CountyBranch])
async def branches(session: SessionDep, _: MembershipOfficer, today: Today):
    """Every county with its branch, published or not, and its officials in office."""
    return await branch_service.by_county(session, today)


def _model(row: BranchOfficial) -> dict:
    return {
        "id": row.id,
        "office": row.office,
        "label": service.label(row),
        "title": row.title,
        "member_id": row.member_id,
        "holder_name": row.holder_name,
        "term_start": row.term_start,
        "term_end": row.term_end,
        "start_reason": row.start_reason,
        "end_reason": row.end_reason,
        "has_minutes": row.minutes_file_id is not None,
        "note": row.note,
        "lapsed": False,
    }


@router.get("/branches/{county_id}/officials/", response_model=OfficialsRead)
async def officials(county_id: uuid.UUID, session: SessionDep, _: MembershipOfficer, today: Today):
    found = await service.officials(session, county_id, today)
    lapsed = found.pop("lapsed")
    return {
        kind: [{**_model(r), "lapsed": r.id in lapsed} for r in rows]
        for kind, rows in found.items()
    }


@router.post(
    "/branches/{county_id}/officials/",
    response_model=OfficialRead,
    status_code=status.HTTP_201_CREATED,
)
async def appoint(
    county_id: uuid.UUID, payload: OfficialAppoint, session: SessionDep, officer: MembershipOfficer
):
    return _model(await service.appoint(session, county_id, payload, actor=officer))


@router.post("/officials/{official_id}/end/", response_model=OfficialRead)
async def end_term(
    official_id: uuid.UUID, payload: OfficialEnd, session: SessionDep, officer: MembershipOfficer
):
    return _model(await service.end_term(session, official_id, payload, actor=officer))


@router.post("/minutes/", response_model=MinutesRead, status_code=status.HTTP_201_CREATED)
async def upload_minutes(
    file: UploadFile, session: SessionDep, officer: MembershipOfficer
) -> MinutesRead:
    """Signed minutes of the meeting, as a PDF or a photo; private to the party office."""
    stored = await store_upload(session, file, area=FileArea.MINUTES, public=False, actor=officer)
    return MinutesRead(id=stored.id, name=stored.original_name)


@router.get("/officials/{official_id}/minutes/")
async def minutes(
    official_id: uuid.UUID, session: SessionDep, _: MembershipOfficer
) -> FileResponse:
    stored = await service.minutes_of(session, official_id)
    return private_file(stored, "The minutes file is missing.")
