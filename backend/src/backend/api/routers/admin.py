"""The admin console: every campaign and login on the deployment, for a superuser only."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from backend.api.deps import AdminUser, SessionDep, Today
from backend.models import (
    AgendaIssue,
    HeroSlide,
    PartyDocument,
    PartyOrgan,
    PartyRoleName,
    PartyValue,
    PartyVideo,
    PostKind,
    PrimaryResult,
    UserRole,
)
from backend.schemas.admin import (
    ActiveSet,
    AdminCampaignCreate,
    AdminCampaignCreated,
    AdminCampaignRead,
    AdminUserCreate,
    AdminUserCreated,
    AdminUserRead,
    CampaignRename,
    MemberAdd,
    Overview,
    PartyMemberLink,
    PartyRoleGrant,
    PasswordReset,
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
    PostAdminRead,
    PostCreate,
    PostUpdate,
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
from backend.schemas.party import PartySettingsRead, PartySettingsUpdate
from backend.schemas.site import SiteSettingsRead, SiteSettingsUpdate
from backend.services import admin as service
from backend.services import audit, branches, candidates, content, home
from backend.services import party as party_service
from backend.services import site as site_service
from backend.services.errors import Refused

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview/", response_model=Overview)
async def overview(session: SessionDep, _: AdminUser) -> Overview:
    return Overview(
        totals=await service.totals(session), campaigns=await service.campaigns(session)
    )


@router.get("/party/leaders/", response_model=list[LeaderAdminRead])
async def party_leaders(session: SessionDep, _: AdminUser):
    """Every leader, published or not."""
    return await content.leaders(session)


@router.post("/party/leaders/", response_model=LeaderAdminRead, status_code=status.HTTP_201_CREATED)
async def create_party_leader(payload: LeaderCreate, session: SessionDep, admin: AdminUser):
    return await content.create_leader(session, payload, actor=admin)


@router.patch("/party/leaders/{leader_id}/", response_model=LeaderAdminRead)
async def update_party_leader(
    leader_id: uuid.UUID, payload: LeaderUpdate, session: SessionDep, admin: AdminUser
):
    return await content.update_leader(session, leader_id, payload, actor=admin)


@router.delete("/party/leaders/{leader_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_party_leader(leader_id: uuid.UUID, session: SessionDep, admin: AdminUser):
    await content.delete_leader(session, leader_id, actor=admin)


@router.get("/party/posts/", response_model=list[PostAdminRead])
async def party_posts(session: SessionDep, _: AdminUser, kind: PostKind | None = None):
    """Every post, drafts included, newest first."""
    return await content.posts(session, kind)


@router.post("/party/posts/", response_model=PostAdminRead, status_code=status.HTTP_201_CREATED)
async def create_party_post(
    payload: PostCreate, session: SessionDep, admin: AdminUser, today: Today
):
    """Add a post; publishing it sets its published date to today."""
    return await content.create_post(session, payload, actor=admin, on=today)


@router.patch("/party/posts/{post_id}/", response_model=PostAdminRead)
async def update_party_post(
    post_id: uuid.UUID, payload: PostUpdate, session: SessionDep, admin: AdminUser, today: Today
):
    """Change a post; the first publish sets its published date, later ones keep it."""
    return await content.update_post(session, post_id, payload, actor=admin, on=today)


@router.delete("/party/posts/{post_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_party_post(post_id: uuid.UUID, session: SessionDep, admin: AdminUser):
    await content.delete_post(session, post_id, actor=admin)


@router.get("/party/branches/", response_model=list[CountyBranch])
async def party_branches(session: SessionDep, _: AdminUser):
    """Every county with its branch, published or not."""
    return await branches.by_county(session)


@router.put("/party/branches/{county_id}/", response_model=BranchAdminRead)
async def save_party_branch(
    county_id: uuid.UUID, payload: BranchUpdate, session: SessionDep, admin: AdminUser
):
    return await branches.save(session, county_id, payload, actor=admin)


@router.put("/party/", response_model=PartySettingsRead)
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


@router.post(
    "/campaigns/", response_model=AdminCampaignCreated, status_code=status.HTTP_201_CREATED
)
async def create_campaign(
    payload: AdminCampaignCreate, session: SessionDep, admin: AdminUser
) -> AdminCampaignCreated:
    """Create a campaign with its aspirant's and manager's logins; passwords are shown once."""
    created, summary, logins = await service.create_campaign(
        session,
        actor=admin,
        **payload.model_dump(exclude={"aspirant", "manager"}),
        aspirant=payload.aspirant.model_dump(),
        manager=payload.manager.model_dump() if payload.manager else None,
    )
    return AdminCampaignCreated(
        campaign=await service.campaign(session, created.id),
        setup=summary,
        logins=[
            AdminUserCreated(
                id=login.id,
                username=login.username,
                full_name=login.full_name,
                role=login.role,
                password=password,
            )
            for login, password in logins
        ],
    )


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
) -> list[AdminUserRead]:
    return await service.users(session, role=role, campaign_id=campaign)


@router.post("/users/", response_model=AdminUserCreated, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: AdminUserCreate, session: SessionDep, admin: AdminUser
) -> AdminUserCreated:
    """Create a login; its password is shown once."""
    created, password = await service.create_user(
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
        password=password,
    )


@router.post("/users/{user_id}/reset-password/", response_model=PasswordResult)
async def reset_password(
    user_id: uuid.UUID, payload: PasswordReset, session: SessionDep, admin: AdminUser
) -> PasswordResult:
    """Hand out a new password; the login's session is signed out."""
    password = await service.reset_password(session, user_id, payload.password, actor=admin)
    return PasswordResult(
        username=(await service.user(session, user_id)).username, password=password
    )


@router.post("/users/{user_id}/active/", response_model=AdminUserRead)
async def set_active(
    user_id: uuid.UUID, payload: ActiveSet, session: SessionDep, admin: AdminUser
) -> AdminUserRead:
    if user_id == admin.id:
        raise Refused("You cannot disable your own login.")
    await service.set_active(session, user_id, payload.active, actor=admin)
    return await service.user(session, user_id)


@router.post(
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


@router.put("/users/{user_id}/party-member/", response_model=AdminUserRead)
async def link_party_member(
    user_id: uuid.UUID, payload: PartyMemberLink, session: SessionDep, admin: AdminUser
) -> AdminUserRead:
    """Link a login to the party member it belongs to, or unlink it with null."""
    await service.link_party_member(session, user_id, payload.member, actor=admin)
    return await service.user(session, user_id)


@router.delete("/users/{user_id}/party-roles/{role}/", status_code=status.HTTP_204_NO_CONTENT)
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
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[AuditEventRead]:
    """The audit trail, newest first."""
    return await audit.events(
        session, subject_type=subject_type, subject_id=subject_id, limit=limit
    )


@router.get("/party/slides/", response_model=list[SlideAdminRead])
async def party_slides(session: SessionDep, _: AdminUser):
    return await home.every(session, HeroSlide)


@router.post("/party/slides/", response_model=SlideAdminRead, status_code=status.HTTP_201_CREATED)
async def create_party_slide(payload: SlideCreate, session: SessionDep, admin: AdminUser):
    return await home.create(session, HeroSlide, payload, actor=admin)


@router.patch("/party/slides/{slide_id}/", response_model=SlideAdminRead)
async def update_party_slide(
    slide_id: uuid.UUID, payload: SlideUpdate, session: SessionDep, admin: AdminUser
):
    return await home.update(session, HeroSlide, slide_id, payload, actor=admin)


@router.delete("/party/slides/{slide_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_party_slide(slide_id: uuid.UUID, session: SessionDep, admin: AdminUser):
    await home.delete(session, HeroSlide, slide_id, actor=admin)


@router.get("/party/issues/", response_model=list[IssueAdminRead])
async def party_issues(session: SessionDep, _: AdminUser):
    return await home.every(session, AgendaIssue)


@router.post("/party/issues/", response_model=IssueAdminRead, status_code=status.HTTP_201_CREATED)
async def create_party_issue(payload: IssueCreate, session: SessionDep, admin: AdminUser):
    return await home.create(session, AgendaIssue, payload, actor=admin)


@router.patch("/party/issues/{issue_id}/", response_model=IssueAdminRead)
async def update_party_issue(
    issue_id: uuid.UUID, payload: IssueUpdate, session: SessionDep, admin: AdminUser
):
    return await home.update(session, AgendaIssue, issue_id, payload, actor=admin)


@router.delete("/party/issues/{issue_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_party_issue(issue_id: uuid.UUID, session: SessionDep, admin: AdminUser):
    await home.delete(session, AgendaIssue, issue_id, actor=admin)


@router.get("/party/documents/", response_model=list[DocumentAdminRead])
async def party_documents(session: SessionDep, _: AdminUser):
    return await home.every(session, PartyDocument)


@router.post(
    "/party/documents/", response_model=DocumentAdminRead, status_code=status.HTTP_201_CREATED
)
async def create_party_document(payload: DocumentCreate, session: SessionDep, admin: AdminUser):
    return await home.create(session, PartyDocument, payload, actor=admin)


@router.patch("/party/documents/{document_id}/", response_model=DocumentAdminRead)
async def update_party_document(
    document_id: uuid.UUID, payload: DocumentUpdate, session: SessionDep, admin: AdminUser
):
    return await home.update(session, PartyDocument, document_id, payload, actor=admin)


@router.delete("/party/documents/{document_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_party_document(document_id: uuid.UUID, session: SessionDep, admin: AdminUser):
    await home.delete(session, PartyDocument, document_id, actor=admin)


@router.get("/party/values/", response_model=list[AboutItemAdminRead])
async def party_values(session: SessionDep, _: AdminUser):
    return await home.every(session, PartyValue)


@router.post(
    "/party/values/", response_model=AboutItemAdminRead, status_code=status.HTTP_201_CREATED
)
async def create_party_value(payload: AboutItemCreate, session: SessionDep, admin: AdminUser):
    return await home.create(session, PartyValue, payload, actor=admin)


@router.patch("/party/values/{value_id}/", response_model=AboutItemAdminRead)
async def update_party_value(
    value_id: uuid.UUID, payload: AboutItemUpdate, session: SessionDep, admin: AdminUser
):
    return await home.update(session, PartyValue, value_id, payload, actor=admin)


@router.delete("/party/values/{value_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_party_value(value_id: uuid.UUID, session: SessionDep, admin: AdminUser):
    await home.delete(session, PartyValue, value_id, actor=admin)


@router.get("/party/organs/", response_model=list[AboutItemAdminRead])
async def party_organs(session: SessionDep, _: AdminUser):
    return await home.every(session, PartyOrgan)


@router.post(
    "/party/organs/", response_model=AboutItemAdminRead, status_code=status.HTTP_201_CREATED
)
async def create_party_organ(payload: AboutItemCreate, session: SessionDep, admin: AdminUser):
    return await home.create(session, PartyOrgan, payload, actor=admin)


@router.patch("/party/organs/{organ_id}/", response_model=AboutItemAdminRead)
async def update_party_organ(
    organ_id: uuid.UUID, payload: AboutItemUpdate, session: SessionDep, admin: AdminUser
):
    return await home.update(session, PartyOrgan, organ_id, payload, actor=admin)


@router.delete("/party/organs/{organ_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_party_organ(organ_id: uuid.UUID, session: SessionDep, admin: AdminUser):
    await home.delete(session, PartyOrgan, organ_id, actor=admin)


@router.get("/party/results/", response_model=list[ResultAdminRead])
async def party_results(session: SessionDep, _: AdminUser):
    return await home.every(session, PrimaryResult)


@router.post("/party/results/", response_model=ResultAdminRead, status_code=status.HTTP_201_CREATED)
async def create_party_result(payload: ResultCreate, session: SessionDep, admin: AdminUser):
    return await home.create(session, PrimaryResult, payload, actor=admin)


@router.patch("/party/results/{result_id}/", response_model=ResultAdminRead)
async def update_party_result(
    result_id: uuid.UUID, payload: ResultUpdate, session: SessionDep, admin: AdminUser
):
    return await home.update(session, PrimaryResult, result_id, payload, actor=admin)


@router.delete("/party/results/{result_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_party_result(result_id: uuid.UUID, session: SessionDep, admin: AdminUser):
    await home.delete(session, PrimaryResult, result_id, actor=admin)


@router.get("/party/videos/", response_model=list[VideoAdminRead])
async def party_videos(session: SessionDep, _: AdminUser):
    return await home.every(session, PartyVideo)


@router.post("/party/videos/", response_model=VideoAdminRead, status_code=status.HTTP_201_CREATED)
async def create_party_video(payload: VideoCreate, session: SessionDep, admin: AdminUser):
    return await home.create(session, PartyVideo, payload, actor=admin)


@router.patch("/party/videos/{video_id}/", response_model=VideoAdminRead)
async def update_party_video(
    video_id: uuid.UUID, payload: VideoUpdate, session: SessionDep, admin: AdminUser
):
    return await home.update(session, PartyVideo, video_id, payload, actor=admin)


@router.delete("/party/videos/{video_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_party_video(video_id: uuid.UUID, session: SessionDep, admin: AdminUser):
    await home.delete(session, PartyVideo, video_id, actor=admin)


@router.get("/party/candidates/", response_model=list[CandidateAdminRead])
async def party_candidates(session: SessionDep, _: AdminUser):
    """Every approved aspirant with the profile written so far."""
    return await candidates.approved_with_profiles(session)


@router.get("/party/candidates/{aspirant_id}/profile/", response_model=CandidateAdminRead)
async def candidate_profile(aspirant_id: uuid.UUID, session: SessionDep, _: AdminUser):
    return await candidates.read_profile(session, aspirant_id)


@router.put("/party/candidates/{aspirant_id}/profile/", response_model=CandidateAdminRead)
async def write_candidate_profile(
    aspirant_id: uuid.UUID, payload: ProfileWrite, session: SessionDep, admin: AdminUser
):
    """Write and publish an approved aspirant's profile; the request replaces it."""
    return await candidates.write_profile(session, aspirant_id, payload, actor=admin)


@router.get("/party/posts/{post_id}/aspirants/", response_model=PostAspirants)
async def post_aspirants(post_id: uuid.UUID, session: SessionDep, _: AdminUser):
    return PostAspirants(aspirant_ids=await candidates.post_aspirants(session, post_id))


@router.put("/party/posts/{post_id}/aspirants/", response_model=PostAspirants)
async def set_post_aspirants(
    post_id: uuid.UUID, payload: PostAspirants, session: SessionDep, admin: AdminUser
):
    """The approved aspirants an event names; it shows on each one's profile."""
    ids = await candidates.set_post_aspirants(session, post_id, payload.aspirant_ids, actor=admin)
    return PostAspirants(aspirant_ids=ids)
