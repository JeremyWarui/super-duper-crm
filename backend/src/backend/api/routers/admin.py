"""The admin console: every campaign and login on the deployment, for a superuser only."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from backend.api.deps import AdminUser, SessionDep
from backend.models import PartyRoleName, UserRole
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
    PartyRoleGrant,
    PasswordReset,
    PasswordResult,
)
from backend.schemas.audit import AuditEventRead
from backend.schemas.party import PartySettingsRead, PartySettingsUpdate
from backend.services import admin as service
from backend.services import audit
from backend.services import party as party_service
from backend.services.errors import Refused

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview/", response_model=Overview)
async def overview(session: SessionDep, _: AdminUser) -> Overview:
    return Overview(
        totals=await service.totals(session), campaigns=await service.campaigns(session)
    )


@router.put("/party/", response_model=PartySettingsRead)
async def update_party(
    payload: PartySettingsUpdate, session: SessionDep, admin: AdminUser
) -> PartySettingsRead:
    """Replace the party's settings."""
    return await party_service.update_settings(session, payload, actor=admin)


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
