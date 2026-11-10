"""The admin console: every campaign and login on the deployment, for a superuser only."""

import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import select

from backend.api.content_routes import items, posts
from backend.api.deps import AdminUser, SessionDep, Today
from backend.api.install import PartyOnlyRoute
from backend.models import (
    AgendaIssue,
    HeroSlide,
    ImportRun,
    PartyDocument,
    PartyOrgan,
    PartyRoleName,
    PartyValue,
    PartyVideo,
    PrimaryResult,
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
    PartyMemberLink,
    PartyRoleGrant,
    PasswordResult,
)
from backend.schemas.audit import AuditEventRead
from backend.schemas.candidates import CandidateAdminRead, PostAspirants, ProfileWrite
from backend.schemas.content import (
    AboutItemAdminRead,
    AboutItemCreate,
    AboutItemUpdate,
    BranchAdminRead,
    BranchUpdate,
    CountyBranch,
    DocumentAdminRead,
    DocumentCreate,
    DocumentUpdate,
    IssueAdminRead,
    IssueCreate,
    IssueUpdate,
    LeaderAdminRead,
    LeaderCreate,
    LeaderUpdate,
    ResultAdminRead,
    ResultCreate,
    ResultUpdate,
    SlideAdminRead,
    SlideCreate,
    SlideUpdate,
    VideoAdminRead,
    VideoCreate,
    VideoUpdate,
)
from backend.schemas.imports import SHOWN_CHANGES, ImportReportRead, ImportRunRead, ImportUpload
from backend.schemas.party import PartySettingsRead, PartySettingsUpdate
from backend.schemas.site import SiteSettingsRead, SiteSettingsUpdate
from backend.services import admin as service
from backend.services import audit, branches, candidates, content, imports
from backend.services import party as party_service
from backend.services import site as site_service
from backend.services.errors import Refused

router = APIRouter(prefix="/admin", tags=["admin"])
# Mounted in every installation; party_router only in a party installation.
party_router = APIRouter(prefix="/admin", tags=["admin"], route_class=PartyOnlyRoute)


@router.get("/overview/", response_model=Overview)
async def overview(session: SessionDep, _: AdminUser) -> Overview:
    return Overview(
        totals=await service.totals(session), campaigns=await service.campaigns(session)
    )


@party_router.get("/party/leaders/", response_model=list[LeaderAdminRead])
async def party_leaders(session: SessionDep, _: AdminUser):
    """Every leader, published or not."""
    return await content.leaders(session)


@party_router.post(
    "/party/leaders/", response_model=LeaderAdminRead, status_code=status.HTTP_201_CREATED
)
async def create_party_leader(payload: LeaderCreate, session: SessionDep, admin: AdminUser):
    return await content.create_leader(session, payload, actor=admin)


@party_router.patch("/party/leaders/{leader_id}/", response_model=LeaderAdminRead)
async def update_party_leader(
    leader_id: uuid.UUID, payload: LeaderUpdate, session: SessionDep, admin: AdminUser
):
    return await content.update_leader(session, leader_id, payload, actor=admin)


@party_router.delete("/party/leaders/{leader_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_party_leader(leader_id: uuid.UUID, session: SessionDep, admin: AdminUser):
    await content.delete_leader(session, leader_id, actor=admin)


posts(router, AdminUser, "/party/posts/")


@party_router.get("/party/branches/", response_model=list[CountyBranch])
async def party_branches(session: SessionDep, _: AdminUser, today: Today):
    """Every county with its branch, published or not, and its officials in office."""
    return await branches.by_county(session, today)


@party_router.put("/party/branches/{county_id}/", response_model=BranchAdminRead)
async def save_party_branch(
    county_id: uuid.UUID, payload: BranchUpdate, session: SessionDep, admin: AdminUser, today: Today
):
    return await branches.save(session, county_id, payload, actor=admin, today=today)


@party_router.put("/party/", response_model=PartySettingsRead)
async def update_party(
    payload: PartySettingsUpdate, session: SessionDep, admin: AdminUser
) -> PartySettingsRead:
    """Replace the party-only settings."""
    return await party_service.update_settings(session, payload, actor=admin)


@router.put("/site/", response_model=SiteSettingsRead)
async def update_site(
    payload: SiteSettingsUpdate, session: SessionDep, admin: AdminUser
) -> SiteSettingsRead:
    """Replace the site settings; the organisation type stays as setup wrote it."""
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
async def delete_campaign(
    campaign_id: uuid.UUID, session: SessionDep, admin: AdminUser
) -> Response:
    """Delete a campaign, everything on it, and its people's logins."""
    await service.delete_campaign(session, campaign_id, actor=admin)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
) -> Response:
    await service.remove_member(session, campaign_id, user_id, actor=admin)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
    return AdminUserCreated(
        id=created.id,
        username=created.username,
        full_name=created.full_name,
        role=created.role,
        invite=invite,
    )


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


@party_router.post(
    "/users/{user_id}/party-roles/",
    response_model=AdminUserRead,
    status_code=status.HTTP_201_CREATED,
)
async def grant_party_role(
    user_id: uuid.UUID, payload: PartyRoleGrant, session: SessionDep, admin: AdminUser
) -> AdminUserRead:
    """Give a staff login a party office."""
    await service.grant_party_role(session, user_id, payload.role, actor=admin)
    return await service.user(session, user_id)


@party_router.put("/users/{user_id}/party-member/", response_model=AdminUserRead)
async def link_party_member(
    user_id: uuid.UUID, payload: PartyMemberLink, session: SessionDep, admin: AdminUser
) -> AdminUserRead:
    """Link a login to the party member it belongs to, or unlink it with null."""
    await service.link_party_member(session, user_id, payload.member, actor=admin)
    return await service.user(session, user_id)


@party_router.delete("/users/{user_id}/party-roles/{role}/", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_party_role(
    user_id: uuid.UUID, role: PartyRoleName, session: SessionDep, admin: AdminUser
) -> Response:
    """Take a party office from a login."""
    await service.revoke_party_role(session, user_id, role, actor=admin)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


items(
    router,
    AdminUser,
    "/party/slides/",
    HeroSlide,
    SlideCreate,
    SlideUpdate,
    SlideAdminRead,
    key="slide_id",
)
items(
    router,
    AdminUser,
    "/party/issues/",
    AgendaIssue,
    IssueCreate,
    IssueUpdate,
    IssueAdminRead,
    key="issue_id",
)
items(
    router,
    AdminUser,
    "/party/documents/",
    PartyDocument,
    DocumentCreate,
    DocumentUpdate,
    DocumentAdminRead,
    key="document_id",
)
items(
    party_router,
    AdminUser,
    "/party/values/",
    PartyValue,
    AboutItemCreate,
    AboutItemUpdate,
    AboutItemAdminRead,
    key="value_id",
)
items(
    party_router,
    AdminUser,
    "/party/organs/",
    PartyOrgan,
    AboutItemCreate,
    AboutItemUpdate,
    AboutItemAdminRead,
    key="organ_id",
)
items(
    party_router,
    AdminUser,
    "/party/results/",
    PrimaryResult,
    ResultCreate,
    ResultUpdate,
    ResultAdminRead,
    key="result_id",
)
items(
    router,
    AdminUser,
    "/party/videos/",
    PartyVideo,
    VideoCreate,
    VideoUpdate,
    VideoAdminRead,
    key="video_id",
)


@party_router.get("/party/candidates/", response_model=list[CandidateAdminRead])
async def party_candidates(session: SessionDep, _: AdminUser):
    """Every approved aspirant with the profile written so far."""
    return await candidates.approved_with_profiles(session)


@party_router.get("/party/candidates/{aspirant_id}/profile/", response_model=CandidateAdminRead)
async def candidate_profile(aspirant_id: uuid.UUID, session: SessionDep, _: AdminUser):
    return await candidates.read_profile(session, aspirant_id)


@party_router.put("/party/candidates/{aspirant_id}/profile/", response_model=CandidateAdminRead)
async def write_candidate_profile(
    aspirant_id: uuid.UUID, payload: ProfileWrite, session: SessionDep, admin: AdminUser
):
    """Write and publish an approved aspirant's profile; the request replaces it."""
    return await candidates.write_profile(session, aspirant_id, payload, actor=admin)


@party_router.get("/party/posts/{post_id}/aspirants/", response_model=PostAspirants)
async def post_aspirants(post_id: uuid.UUID, session: SessionDep, _: AdminUser):
    return PostAspirants(aspirant_ids=await candidates.post_aspirants(session, post_id))


@party_router.put("/party/posts/{post_id}/aspirants/", response_model=PostAspirants)
async def set_post_aspirants(
    post_id: uuid.UUID, payload: PostAspirants, session: SessionDep, admin: AdminUser
):
    """The approved aspirants an event names; it shows on each one's profile."""
    ids = await candidates.set_post_aspirants(session, post_id, payload.aspirant_ids, actor=admin)
    return PostAspirants(aspirant_ids=ids)


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
