"""Mobilizer logins, added and removed by a campaign's manager or candidate."""

import uuid

from fastapi import APIRouter, HTTPException, Response, status

from backend.api.deps import SessionDep, TeamWriter
from backend.api.scope import require_visible_campaign, require_ward_in_campaign, visible_user_ids
from backend.models import User, UserRole, Ward
from backend.schemas.user import UserCreate, UserCreated
from backend.services.accounts import add_mobilizer, new_login

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserCreated, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, session: SessionDep, user: TeamWriter) -> UserCreated:
    """Create a mobilizer's login on a ward of the caller's campaign; the password is shown once."""
    campaign = await require_visible_campaign(session, user, payload.campaign)
    ward = await session.get(Ward, payload.ward)
    if ward is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No such ward.")
    await require_ward_in_campaign(session, campaign, ward.id, payload.registration_centre)

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
        session, campaign, ward.id, created, centre_id=payload.registration_centre
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
        ward_name=ward.name,
    )


@router.delete("/{user_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: uuid.UUID, session: SessionDep, user: TeamWriter) -> Response:
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
    await session.delete(target)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
