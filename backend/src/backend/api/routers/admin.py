"""The admin console: every campaign and login on the deployment, for a superuser only."""

import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from backend.api.deps import AdminUser, SessionDep
from backend.models import (
    ImportRun,
    UserRole,
)
from backend.schemas.admin import (
    ActiveSet,
    AdminCampaignRead,
    AdminUserCreate,
    AdminUserCreated,
    AdminUserRead,
    CampaignRename,
    EmailSet,
    MemberAdd,
    Overview,
    PasswordResult,
)
from backend.schemas.audit import AuditEventRead
from backend.schemas.imports import SHOWN_CHANGES, ImportReportRead, ImportRunRead, ImportUpload
from backend.schemas.site import SiteSettingsRead, SiteSettingsUpdate
from backend.services import admin as service
from backend.services import audit, imports
from backend.services import site as site_service
from backend.services.errors import Refused

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview/", response_model=Overview)
async def overview(session: SessionDep, _: AdminUser) -> Overview:
    return Overview(
        totals=await service.totals(session), campaigns=await service.campaigns(session)
    )


@router.put("/site/", response_model=SiteSettingsRead)
async def update_site(
    payload: SiteSettingsUpdate, session: SessionDep, admin: AdminUser
) -> SiteSettingsRead:
    """Replace the site settings."""
    return await site_service.update_settings(session, payload, actor=admin)


@router.get("/campaigns/", response_model=list[AdminCampaignRead])
async def list_campaigns(session: SessionDep, _: AdminUser) -> list[AdminCampaignRead]:
    return await service.campaigns(session)


@router.get("/campaigns/{campaign_id}/", response_model=AdminCampaignRead)
async def get_campaign(
    campaign_id: uuid.UUID, session: SessionDep, _: AdminUser
) -> AdminCampaignRead:
    return await service.campaign(session, campaign_id)


@router.patch("/campaigns/{campaign_id}/", response_model=AdminCampaignRead)
async def rename_campaign(
    campaign_id: uuid.UUID, payload: CampaignRename, session: SessionDep, admin: AdminUser
) -> AdminCampaignRead:
    await service.rename_campaign(session, campaign_id, payload.title, actor=admin)
    return await service.campaign(session, campaign_id)


@router.delete("/campaigns/{campaign_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(campaign_id: uuid.UUID, session: SessionDep, admin: AdminUser) -> None:
    """Delete a campaign, everything on it, and its people's logins."""
    await service.delete_campaign(session, campaign_id, actor=admin)


@router.post(
    "/campaigns/{campaign_id}/members/",
    response_model=AdminCampaignRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    campaign_id: uuid.UUID, payload: MemberAdd, session: SessionDep, admin: AdminUser
) -> AdminCampaignRead:
    await service.add_member(session, campaign_id, payload.user, actor=admin)
    return await service.campaign(session, campaign_id)


@router.delete(
    "/campaigns/{campaign_id}/members/{user_id}/", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_member(
    campaign_id: uuid.UUID, user_id: uuid.UUID, session: SessionDep, admin: AdminUser
) -> None:
    await service.remove_member(session, campaign_id, user_id, actor=admin)


@router.get("/users/", response_model=list[AdminUserRead])
async def list_users(
    session: SessionDep,
    _: AdminUser,
    role: UserRole | None = None,
    campaign: uuid.UUID | None = None,
    limit: Annotated[int | None, Query(ge=1, le=200)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AdminUserRead]:
    return await service.users(session, role=role, campaign_id=campaign, limit=limit, offset=offset)


@router.post("/users/", response_model=AdminUserCreated, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: AdminUserCreate, session: SessionDep, admin: AdminUser
) -> AdminUserCreated:
    """Create a login and send it an invite link."""
    created, invite = await service.create_user(
        session,
        actor=admin,
        **payload.model_dump(exclude={"campaign", "ward", "registration_centre"}),
        campaign_id=payload.campaign,
        ward_id=payload.ward,
        centre_id=payload.registration_centre,
    )
    return AdminUserCreated.of(created, invite)


@router.post("/users/{user_id}/reset-password/", response_model=PasswordResult)
async def reset_password(
    user_id: uuid.UUID, session: SessionDep, admin: AdminUser
) -> PasswordResult:
    """Send the login a link to choose a new password."""
    sent = await service.reset_password(session, user_id, actor=admin)
    return PasswordResult(username=(await service.user(session, user_id)).username, sent=sent)


@router.post("/users/{user_id}/active/", response_model=AdminUserRead)
async def set_active(
    user_id: uuid.UUID, payload: ActiveSet, session: SessionDep, admin: AdminUser
) -> AdminUserRead:
    if user_id == admin.id:
        raise Refused("You cannot disable your own login.")
    await service.set_active(session, user_id, payload.active, actor=admin)
    return await service.user(session, user_id)


@router.put("/users/{user_id}/email/", response_model=AdminUserRead)
async def set_email(
    user_id: uuid.UUID, payload: EmailSet, session: SessionDep, admin: AdminUser
) -> AdminUserRead:
    """Change the email a login signs in with."""
    await service.set_email(session, user_id, payload.email, actor=admin)
    return await service.user(session, user_id)


@router.get("/audit/", response_model=list[AuditEventRead])
async def audit_events(
    session: SessionDep,
    _: AdminUser,
    subject_type: str | None = None,
    subject_id: uuid.UUID | None = None,
    action: Annotated[str | None, Query(max_length=60)] = None,
    actor: Annotated[str | None, Query(max_length=150)] = None,
    since: date | Literal[""] = "",
    until: date | Literal[""] = "",
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AuditEventRead]:
    """The audit trail, newest first, filtered by action, who did it and when."""
    return await audit.events(
        session,
        subject_type=subject_type,
        subject_id=subject_id,
        action=action,
        actor=actor,
        since=since or None,
        until=until or None,
        limit=limit,
        offset=offset,
    )


@router.post("/imports/boundaries/", response_model=ImportReportRead)
async def import_boundaries(
    payload: ImportUpload, session: SessionDep, admin: AdminUser
) -> ImportReportRead:
    report = await imports.import_boundaries(
        session, payload.csv, filename=payload.filename, actor=admin, dry_run=payload.dry_run
    )
    return _report(report)


@router.post("/imports/register/", response_model=ImportReportRead)
async def import_register(
    payload: ImportUpload, session: SessionDep, admin: AdminUser
) -> ImportReportRead:
    report = await imports.import_register(
        session, payload.csv, filename=payload.filename, actor=admin, dry_run=payload.dry_run
    )
    return _report(report)


@router.get("/imports/", response_model=list[ImportRunRead])
async def import_runs(session: SessionDep, _: AdminUser) -> list[ImportRun]:
    runs = await session.scalars(select(ImportRun).order_by(ImportRun.created_at.desc()).limit(20))
    return list(runs)


def _report(report: imports.ImportReport) -> ImportReportRead:
    return ImportReportRead(
        kind=report.kind,
        rows=report.rows,
        applied=report.applied,
        counts=report.counts,
        changes=[vars(c) for c in report.changes[:SHOWN_CHANGES]],
    )
