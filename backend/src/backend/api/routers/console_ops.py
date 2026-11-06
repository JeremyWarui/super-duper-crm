"""The console's Health, Export, backups and test sends; superuser only."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select

from backend.api.deps import AdminUser, SessionDep, get_organisation_type
from backend.models import BackupRun, OrganisationType
from backend.schemas.ops import BackupRunRead, Health, TestResult, TestSend
from backend.services import ops

router = APIRouter(prefix="/admin", tags=["admin"])
Kind = Annotated[OrganisationType | None, Depends(get_organisation_type)]


@router.get("/health/", response_model=Health)
async def health(session: SessionDep, _: AdminUser, kind: Kind) -> dict:
    return await ops.health(session, kind)


@router.get("/export/")
async def export(session: SessionDep, admin: AdminUser, kind: Kind) -> Response:
    """The installation's data as one zip of JSON and CSV; audited."""
    name, data = await ops.export_archive(session, actor=admin, organisation_type=kind)
    return Response(
        data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/backups/", response_model=list[BackupRunRead])
async def backups(session: SessionDep, _: AdminUser) -> list[BackupRun]:
    runs = await session.scalars(select(BackupRun).order_by(BackupRun.created_at.desc()).limit(20))
    return list(runs)


@router.post("/test/sms/", response_model=TestResult)
async def test_sms(payload: TestSend, session: SessionDep, admin: AdminUser) -> TestResult:
    return TestResult(message=await ops.test_sms(session, payload.phone, actor=admin))


@router.post("/test/payout/", response_model=TestResult)
async def test_payout(payload: TestSend, session: SessionDep, admin: AdminUser) -> TestResult:
    return TestResult(message=await ops.test_payout(session, payload.phone, actor=admin))
