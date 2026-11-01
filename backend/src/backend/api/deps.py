"""Request dependencies: the session, the signed-in caller, and role guards."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.session import get_session
from backend.models import (
    Aspirant,
    AspirantStatus,
    AuthToken,
    CampaignMember,
    PartyMember,
    PartyMemberStatus,
    PartyRoleName,
    User,
    UserRole,
)
from backend.services import membership
from backend.services.errors import CampaignClosed

SessionDep = Annotated[AsyncSession, Depends(get_session)]

TOKEN_SCHEME = "Token"
_header = APIKeyHeader(name="Authorization", auto_error=False, scheme_name="Token")


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": TOKEN_SCHEME}
    )


async def get_signed_in_user(
    session: SessionDep, header: Annotated[str | None, Depends(_header)]
) -> User:
    """The caller named by "Authorization: Token <key>"; 401 when absent or unknown."""
    if not header:
        raise _unauthorized("Authentication credentials were not provided.")
    scheme, _, key = header.partition(" ")
    if scheme != TOKEN_SCHEME or not key.strip():
        raise _unauthorized("Invalid token.")
    token = await session.scalar(
        select(AuthToken)
        .where(AuthToken.key == key.strip())
        .options(
            selectinload(AuthToken.user).selectinload(User.mobilizer_profile),
            selectinload(AuthToken.user).selectinload(User.party_roles),
        )
    )
    if token is None or not token.user.is_active:
        raise _unauthorized("Invalid token.")
    return token.user


SignedInUser = Annotated[User, Depends(get_signed_in_user)]

SUSPENDED = "This campaign is suspended by the party."
CLOSED = "This campaign is closed: its aspirant has withdrawn."


async def get_current_user(user: SignedInUser, session: SessionDep) -> User:
    """The signed-in caller, refused while their campaign's aspirant is not approved."""
    if user.role is not None and not user.is_superuser:
        aspirant = await session.scalar(
            select(Aspirant.status)
            .join(CampaignMember, CampaignMember.campaign_id == Aspirant.campaign_id)
            .where(CampaignMember.user_id == user.id)
        )
        if aspirant is AspirantStatus.SUSPENDED:
            raise CampaignClosed(SUSPENDED)
        if aspirant is not None and aspirant is not AspirantStatus.APPROVED:
            raise CampaignClosed(CLOSED)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: UserRole, message: str | None = None):
    """A guard letting only these roles through; 403 otherwise."""

    async def dependency(user: CurrentUser) -> User:
        if user.role is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, message or "This login has no campaign role."
            )
        if user.role not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, message or f"A {user.role.label} may not change this."
            )
        return user

    return dependency


async def require_superuser(user: CurrentUser) -> User:
    if not user.is_superuser:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This is not yours to see.")
    return user


def require_party_role(*roles: PartyRoleName):
    """A guard letting through a superuser, or a holder of one of these offices whose login is
    linked to an approved party member.

    Applies the party inbox first, so a queued withdrawal of the officer's own membership
    stops them on this request, not the next.
    """

    async def dependency(user: CurrentUser, session: SessionDep) -> User:
        if user.is_superuser:
            return user
        if not any(held.role in roles for held in user.party_roles):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "This needs a party office you do not hold."
            )
        await membership.process_requests(session)
        own = (
            await session.scalar(
                select(PartyMember.status).where(PartyMember.id == user.party_member_id)
            )
            if user.party_member_id
            else None
        )
        if own is not PartyMemberStatus.APPROVED:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "This login needs to be linked to an approved party member.",
            )
        return user

    return dependency


AdminUser = Annotated[User, Depends(require_superuser)]
MembershipOfficer = Annotated[User, Depends(require_party_role(PartyRoleName.MEMBERSHIP_OFFICER))]
NominationsOfficer = Annotated[User, Depends(require_party_role(PartyRoleName.NOMINATIONS_OFFICER))]
Writer = Annotated[User, Depends(require_role(UserRole.MANAGER))]
MobilizerWriter = Annotated[User, Depends(require_role(UserRole.MANAGER, UserRole.MOBILIZER))]
TeamWriter = Annotated[
    User,
    Depends(
        require_role(
            UserRole.MANAGER,
            UserRole.CANDIDATE,
            message="Only a candidate or a campaign manager may add or remove people.",
        )
    ),
]
SupporterTeam = Annotated[
    User,
    Depends(
        require_role(
            UserRole.MANAGER,
            UserRole.MOBILIZER,
            message="The supporter register is for the campaign team.",
        )
    ),
]
