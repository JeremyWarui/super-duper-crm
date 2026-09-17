"""The admin console: every campaign and login on the deployment, for a superuser only."""

import uuid

from fastapi import APIRouter, Response, status

from backend.api.deps import AdminUser, SessionDep
from backend.models import UserRole
from backend.schemas.admin import (
    ActiveSet,
    AdminCampaignRead,
    AdminUserCreate,
    AdminUserCreated,
    AdminUserRead,
    CampaignRename,
    MemberAdd,
    Overview,
    PasswordReset,
    PasswordResult,
)
from backend.services import admin as service
from backend.services.errors import Refused

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview/", response_model=Overview)
async def overview(session: SessionDep, _: AdminUser) -> Overview:
    return Overview(
        totals=await service.totals(session), campaigns=await service.campaigns(session)
    )


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
    campaign_id: uuid.UUID, payload: CampaignRename, session: SessionDep, _: AdminUser
) -> AdminCampaignRead:
    await service.rename_campaign(session, campaign_id, payload.title)
    return await service.campaign(session, campaign_id)


@router.delete("/campaigns/{campaign_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(campaign_id: uuid.UUID, session: SessionDep, _: AdminUser) -> Response:
    """Delete a campaign, everything on it, and its people's logins."""
    await service.delete_campaign(session, campaign_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/campaigns/{campaign_id}/members/",
    response_model=AdminCampaignRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    campaign_id: uuid.UUID, payload: MemberAdd, session: SessionDep, _: AdminUser
) -> AdminCampaignRead:
    await service.add_member(session, campaign_id, payload.user)
    return await service.campaign(session, campaign_id)


@router.delete(
    "/campaigns/{campaign_id}/members/{user_id}/", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_member(
    campaign_id: uuid.UUID, user_id: uuid.UUID, session: SessionDep, _: AdminUser
) -> Response:
    await service.remove_member(session, campaign_id, user_id)
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
    payload: AdminUserCreate, session: SessionDep, _: AdminUser
) -> AdminUserCreated:
    """Create a login; its password is shown once."""
    created, password = await service.create_user(
        session,
        **payload.model_dump(exclude={"campaign", "ward"}),
        campaign_id=payload.campaign,
        ward_id=payload.ward,
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
    user_id: uuid.UUID, payload: PasswordReset, session: SessionDep, _: AdminUser
) -> PasswordResult:
    """Hand out a new password; the login's session is signed out."""
    password = await service.reset_password(session, user_id, payload.password)
    return PasswordResult(
        username=(await service.user(session, user_id)).username, password=password
    )


@router.post("/users/{user_id}/active/", response_model=AdminUserRead)
async def set_active(
    user_id: uuid.UUID, payload: ActiveSet, session: SessionDep, admin: AdminUser
) -> AdminUserRead:
    if user_id == admin.id:
        raise Refused("You cannot disable your own login.")
    await service.set_active(session, user_id, payload.active)
    return await service.user(session, user_id)
