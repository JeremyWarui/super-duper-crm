"""The admin console: every campaign on this deployment, and the people on them.

Every route here is gated by `AdminUser`, which is the `is_superuser` flag and
nothing else. None of these handlers touch `backend.api.scope`, so widening
what an admin sees can never widen what a manager sees.
"""

import uuid

from fastapi import APIRouter, HTTPException, Response, status

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

router = APIRouter(prefix="/admin", tags=["admin"])


def _refused(error: service.AdminError) -> HTTPException:
    if isinstance(error, service.NotFound):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(error))
    return HTTPException(status.HTTP_400_BAD_REQUEST, str(error))


async def _one(session: SessionDep, campaign_id: uuid.UUID) -> service.CampaignRow:
    """Read a campaign back after writing to it, or say it has gone."""
    found = await service.campaigns(session, campaign_id)
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such campaign.")
    return found[0]


async def _user(session: SessionDep, user_id: uuid.UUID) -> service.UserRow:
    """Read a login back after changing it, or say it has gone."""
    found = await service.users(session, user_id=user_id)
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such user.")
    return found[0]


@router.get("/overview/", response_model=Overview)
async def overview(session: SessionDep, _: AdminUser) -> Overview:
    """One number per table, and every campaign with its team and its size."""
    return Overview(
        totals=await service.totals(session),
        campaigns=await service.campaigns(session),
    )


@router.get("/campaigns/", response_model=list[AdminCampaignRead])
async def list_campaigns(session: SessionDep, _: AdminUser) -> list[service.CampaignRow]:
    return await service.campaigns(session)


@router.get("/campaigns/{campaign_id}/", response_model=AdminCampaignRead)
async def get_campaign(
    campaign_id: uuid.UUID, session: SessionDep, _: AdminUser
) -> service.CampaignRow:
    return await _one(session, campaign_id)


@router.get("/users/", response_model=list[AdminUserRead])
async def list_users(
    session: SessionDep,
    _: AdminUser,
    role: UserRole | None = None,
    campaign: uuid.UUID | None = None,
) -> list[service.UserRow]:
    return await service.users(session, role=role, campaign_id=campaign)


@router.post("/users/", response_model=AdminUserCreated, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: AdminUserCreate, session: SessionDep, _: AdminUser
) -> AdminUserCreated:
    """Create a login. Its password is returned once and is never stored."""
    try:
        created, password = await service.create_user(
            session,
            username=payload.username,
            role=payload.role,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            phone=payload.phone,
            campaign_id=payload.campaign,
            ward_id=payload.ward,
        )
    except service.AdminError as error:
        raise _refused(error) from error
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
    """Hand out a new password. Every session that login had is signed out."""
    try:
        password = await service.reset_password(session, user_id, payload.password)
    except service.AdminError as error:
        raise _refused(error) from error
    return PasswordResult(username=(await _user(session, user_id)).username, password=password)


@router.post("/users/{user_id}/active/", response_model=AdminUserRead)
async def set_active(
    user_id: uuid.UUID, payload: ActiveSet, session: SessionDep, admin: AdminUser
) -> service.UserRow:
    if user_id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot disable your own login.")
    try:
        await service.set_active(session, user_id, payload.active)
    except service.AdminError as error:
        raise _refused(error) from error
    return await _user(session, user_id)


@router.patch("/campaigns/{campaign_id}/", response_model=AdminCampaignRead)
async def rename_campaign(
    campaign_id: uuid.UUID, payload: CampaignRename, session: SessionDep, _: AdminUser
) -> service.CampaignRow:
    """Rename a campaign. Its people, targets and register are untouched."""
    try:
        await service.rename_campaign(session, campaign_id, payload.title)
    except service.AdminError as error:
        raise _refused(error) from error
    return await _one(session, campaign_id)


@router.delete("/campaigns/{campaign_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(campaign_id: uuid.UUID, session: SessionDep, _: AdminUser) -> Response:
    """Delete a campaign, everything on it, and every non-superuser login on it."""
    try:
        await service.delete_campaign(session, campaign_id)
    except service.AdminError as error:
        raise _refused(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/campaigns/{campaign_id}/members/",
    response_model=AdminCampaignRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    campaign_id: uuid.UUID, payload: MemberAdd, session: SessionDep, _: AdminUser
) -> service.CampaignRow:
    try:
        await service.add_member(session, campaign_id, payload.user)
    except service.AdminError as error:
        raise _refused(error) from error
    return await _one(session, campaign_id)


@router.delete(
    "/campaigns/{campaign_id}/members/{user_id}/", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_member(
    campaign_id: uuid.UUID, user_id: uuid.UUID, session: SessionDep, _: AdminUser
) -> Response:
    try:
        await service.remove_member(session, campaign_id, user_id)
    except service.AdminError as error:
        raise _refused(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
