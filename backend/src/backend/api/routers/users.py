"""Logins for the campaign team. Passwords are generated and shown once."""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from backend.api.deps import CurrentUser, SessionDep
from backend.api.scope import (
    add_member,
    limit_to_campaigns,
    require_visible_campaign,
    require_ward_in_campaign,
    visible_user_ids,
)
from backend.models import Campaign, CampaignMember, Mobilizer, User, UserRole, Ward
from backend.schemas.user import UserCreate, UserCreated, UserRead
from backend.security import hash_password, new_password

router = APIRouter(prefix="/users", tags=["users"])

MAY_CREATE = {UserRole.CANDIDATE, UserRole.MANAGER}


@router.get("/", response_model=list[UserRead])
async def list_users(
    session: SessionDep, user: CurrentUser, role: UserRole | None = None
) -> list[User]:
    """The caller's own team, or just one role of it."""
    if user.role not in MAY_CREATE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the campaign team may see this.")
    statement = select(User).order_by(User.username)
    if role is not None:
        statement = statement.where(User.role == role)
    statement = limit_to_campaigns(statement, User.id, await visible_user_ids(session, user))
    return list((await session.execute(statement)).scalars().all())


@router.post("/", response_model=UserCreated, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, session: SessionDep, user: CurrentUser) -> UserCreated:
    """Create a login. The password is not stored and cannot be fetched again."""
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

    if payload.role is UserRole.MANAGER and user.role is not UserRole.MANAGER:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only a campaign manager may add another. Ask yours, or use "
            "campaign-crm assign-manager.",
        )

    ward: Ward | None = None
    campaign: Campaign | None = None
    if payload.campaign is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"A {payload.role.label.lower()} needs a campaign, or they sign in to nothing.",
        )
    campaign = await require_visible_campaign(session, user, payload.campaign)

    if payload.role is UserRole.MOBILIZER:
        if payload.ward is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "A mobilizer needs a campaign and a ward, or they sign in to nothing.",
            )
        ward = await session.get(Ward, payload.ward)
        if ward is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "No such ward.")
        await require_ward_in_campaign(session, campaign, ward.id, payload.registration_centre)

    password = new_password()
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

    # They sign in to the campaign they were added to, rather than to an empty
    # app asking them to set one up.
    await add_member(session, campaign.id, created.id)

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

    visible = await visible_user_ids(session, user)
    if user_id not in visible:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such user.")

    target = await session.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such user.")
    if target.is_superuser:
        # Whoever runs the deployment is not a campaign's to remove; deleting
        # the last one leaves nobody able to reach the console.
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "That login runs the deployment, not this campaign."
        )
    stands_in = await session.scalar(
        select(CampaignMember.id).where(
            CampaignMember.user_id == user_id, CampaignMember.role == UserRole.CANDIDATE
        )
    )
    if stands_in is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "That account is a candidate with a campaign; delete the campaign first.",
        )

    await session.delete(target)
    await session.commit()
