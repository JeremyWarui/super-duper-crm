"""Logins for the campaign team. Passwords are generated and shown once."""

import secrets
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.api.deps import CurrentUser, SessionDep
from backend.api.scope import require_visible_campaign
from backend.models import Mobilizer, User, UserRole, Ward
from backend.schemas.user import UserCreate, UserCreated, UserRead

router = APIRouter(prefix="/users", tags=["users"])

GENERATED_PASSWORD_BYTES = 9

MAY_CREATE = {UserRole.CANDIDATE, UserRole.MANAGER}


@router.get("/", response_model=list[UserRead])
async def list_users(session: SessionDep, user: CurrentUser) -> list[User]:
    """The team."""
    if user.role not in MAY_CREATE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the campaign team may see this.")
    return list((await session.execute(select(User).order_by(User.username))).scalars().all())


@router.post("/", response_model=UserCreated, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, session: SessionDep, user: CurrentUser) -> UserCreated:
    """Create a login. The password is not stored and cannot be fetched again."""
    from backend.security import hash_password

    if user.role not in MAY_CREATE:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only a candidate or a campaign manager may add people."
        )

    taken = (
        await session.execute(select(User).where(User.username == payload.username))
    ).scalar_one_or_none()
    if taken is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"The username {payload.username} is already taken."
        )

    ward: Ward | None = None
    if payload.role is UserRole.MOBILIZER:
        if payload.campaign is None or payload.ward is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "A mobilizer needs a campaign and a ward, or they sign in to nothing.",
            )
        await require_visible_campaign(session, user, payload.campaign)
        ward = await session.get(Ward, payload.ward)
        if ward is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "No such ward.")

    password = secrets.token_urlsafe(GENERATED_PASSWORD_BYTES)
    created = User(
        username=payload.username,
        role=payload.role,
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone,
        email=payload.email,
        password_hash=hash_password(password),
    )
    session.add(created)
    await session.flush()

    mobilizer: Mobilizer | None = None
    if payload.role is UserRole.MOBILIZER and ward is not None:
        mobilizer = Mobilizer(
            campaign_id=payload.campaign,
            ward_id=ward.id,
            registration_centre_id=payload.registration_centre,
            user_id=created.id,
            full_name=created.full_name or created.username,
            phone=created.phone,
        )
        session.add(mobilizer)

    await session.commit()

    return UserCreated(
        id=created.id,
        username=created.username,
        full_name=created.full_name,
        role=created.role,
        phone=created.phone,
        password=password,
        mobilizer=mobilizer.id if mobilizer is not None else None,
        ward_name=ward.name if ward is not None else None,
    )


@router.delete("/{user_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> None:
    """Remove a login. The mobilizer row it belonged to stays."""
    if user.role not in MAY_CREATE:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only a candidate or a campaign manager may remove people."
        )
    if user_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot remove your own login.")

    target = (
        await session.execute(
            select(User).where(User.id == user_id).options(selectinload(User.campaigns))
        )
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such user.")
    if target.campaigns:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "That account is a candidate with a campaign; delete the campaign first.",
        )

    await session.delete(target)
    await session.commit()
