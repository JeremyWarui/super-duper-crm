"""Request dependencies: the session, the signed-in caller, and role guards."""

from datetime import date
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.session import get_session
from backend.models import (
    AuthToken,
    OrganisationType,
    PartyMember,
    PartyMemberStatus,
    PartyRoleName,
    User,
    UserKind,
)
from backend.services import access, clock, membership, permissions, site
from backend.services.errors import CampaignClosed, NotFound

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
            selectinload(AuthToken.user).selectinload(User.party_member),
        )
    )
    if token is None or not token.user.is_active:
        raise _unauthorized("Invalid token.")
    return token.user


SignedInUser = Annotated[User, Depends(get_signed_in_user)]


async def get_today() -> date:
    return clock.today()


Today = Annotated[date, Depends(get_today)]


async def get_organisation_type(session: SessionDep) -> OrganisationType | None:
    """Party or aspirant; None before setup."""
    try:
        return await site.organisation_type(session)
    except NotFound:
        return None


async def get_current_user(user: SignedInUser, session: SessionDep) -> User:
    """The signed-in caller, refused while their campaign is closed (`services/access.py`).

    A member login is refused: it opens only the member account.
    """
    if user.kind is UserKind.MEMBER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "A member login opens only its account.")
    if user.role is None or user.is_superuser:
        return user
    found = await access.login_access(session, user.id)
    if not found.open:
        raise CampaignClosed(found.reason)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require(action: str, *, whole: bool = False):
    """A guard letting through the roles `services/permissions.py` gives this action; 403
    otherwise. With `whole`, only roles reaching the whole campaign pass.

    How far each role reaches is applied in `api/scope.py`.
    """

    async def dependency(user: CurrentUser) -> User:
        found = permissions.reach(user, action)
        if found is None or (whole and found is not permissions.Reach.ALL):
            raise HTTPException(status.HTTP_403_FORBIDDEN, permissions.refusal(user, action))
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
