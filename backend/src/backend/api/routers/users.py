"""Mobilizer logins, added and removed by whoever may change the campaign's mobilizers."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select

from backend.api.deps import SessionDep, require
from backend.api.scope import (
    require_in_area,
    require_visible_campaign,
    require_ward_in_campaign,
    visible_user_ids,
)
from backend.models import Mobilizer, User, UserRole, Ward
from backend.schemas.user import UserCreate, UserCreated
from backend.services.accounts import add_mobilizer, new_login
from backend.services.audit import record

router = APIRouter(prefix="/users", tags=["users"])
Writer = Annotated[User, Depends(require("mobilizers.write"))]


@router.post("/", response_model=UserCreated, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, session: SessionDep, user: Writer) -> UserCreated:
    """Create a mobilizer's login on the caller's campaign, on a free ward or none.

    The password is shown once.
    """
    campaign = await require_visible_campaign(session, user, payload.campaign)
    ward = await session.get(Ward, payload.ward) if payload.ward is not None else None
    if payload.ward is not None and ward is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No such ward.")
    await require_ward_in_campaign(session, campaign, payload.ward, payload.registration_centre)
    await require_in_area(
        session, user, "mobilizers.write", payload.ward, payload.registration_centre
    )

    created, password = await new_login(
        session,
        username=payload.username,
        role=UserRole.MOBILIZER,
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        phone=payload.phone,
    )
    mobilizer = await add_mobilizer(
        session, campaign, payload.ward, created, centre_id=payload.registration_centre
    )
    record(
        session,
        actor=user,
        action="mobilizer_login.create",
        subject_type="user",
        subject_id=created.id,
        campaign_id=campaign.id,
        detail={"mobilizer_id": str(mobilizer.id)},
    )
    await session.commit()
    return UserCreated(
        id=created.id,
        username=created.username,
        full_name=created.full_name,
        role=created.role,
        phone=created.phone,
        password=password,
        mobilizer=mobilizer.id,
        ward_name=ward.name if ward is not None else None,
    )


@router.delete("/{user_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: uuid.UUID, session: SessionDep, user: Writer) -> Response:
    """Remove a mobilizer's login from the caller's campaign; their ground row stays."""
    if user_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot remove your own login.")
    target = await session.get(User, user_id)
    if target is None or user_id not in await visible_user_ids(session, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such user.")
    if target.role is not UserRole.MOBILIZER:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only a mobilizer is removed from inside a campaign. "
            "An admin can disable any other login.",
        )
    ground = await session.scalar(select(Mobilizer).where(Mobilizer.user_id == target.id))
    await require_in_area(
        session,
        user,
        "mobilizers.write",
        ground.ward_id if ground else None,
        ground.registration_centre_id if ground else None,
    )
    record(
        session,
        actor=user,
        action="mobilizer_login.delete",
        subject_type="user",
        subject_id=target.id,
    )
    await session.delete(target)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
