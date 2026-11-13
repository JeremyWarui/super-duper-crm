"""Request dependencies: the session, the signed-in caller, and role guards."""

import re
from datetime import date
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from backend.db.session import get_session
from backend.models import (
    AuthToken,
    Constituency,
    OrganisationType,
    PartyMember,
    PartyMemberStatus,
    PartyRoleName,
    User,
    UserKind,
    Ward,
)
from backend.services import access, clock, membership, permissions, site
from backend.services.errors import CampaignClosed, Forbidden, NotFound

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


# What a closed campaign's team may still change: their sign-out, and the data protection work.
OPEN_WHEN_CLOSED = re.compile(r"^/api/(auth/|campaigns/[0-9a-f-]+/data/)")


async def get_current_user(user: SignedInUser, session: SessionDep, request: Request) -> User:
    """The signed-in caller, refused while their campaign is closed (`services/access.py`).

    A member login is refused: it opens only the member account.
    """
    if user.kind is UserKind.MEMBER:
        raise Forbidden("A member login opens only its account.")
    if user.role is None or user.is_superuser:
        return user
    found = await access.login_access(session, user.id)
    if not found.open:
        raise CampaignClosed(found.reason)
    if (
        found.read_only
        and request.method not in ("GET", "HEAD", "OPTIONS")
        and not OPEN_WHEN_CLOSED.match(request.url.path)
    ):
        raise Forbidden(found.reason)
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
            raise Forbidden(permissions.refusal(user, action))
        return user

    return dependency


async def require_superuser(user: CurrentUser) -> User:
    if not user.is_superuser:
        raise Forbidden("This is not yours to see.")
    return user


def require_party_role(*roles: PartyRoleName):
    """A guard letting through a superuser, or a holder of one of these offices whose login is
    linked to an approved party member.

    Applies the party inbox first, so the route reads an up-to-date register and a queued
    withdrawal of the officer's own membership stops them on this request, not the next.
    """

    async def dependency(user: CurrentUser, session: SessionDep) -> User:
        if not user.is_superuser and not any(held.role in roles for held in user.party_roles):
            raise Forbidden("This needs a party office you do not hold.")
        await membership.process_requests(session)
        if user.is_superuser:
            return user
        own = (
            await session.scalar(
                select(PartyMember.status).where(PartyMember.id == user.party_member_id)
            )
            if user.party_member_id
            else None
        )
        if own is not PartyMemberStatus.APPROVED:
            raise Forbidden("This login needs to be linked to an approved party member.")
        return user

    return dependency


AdminUser = Annotated[User, Depends(require_superuser)]
MembershipOfficer = Annotated[User, Depends(require_party_role(PartyRoleName.MEMBERSHIP_OFFICER))]
NominationsOfficer = Annotated[User, Depends(require_party_role(PartyRoleName.NOMINATIONS_OFFICER))]


async def account_member(session: AsyncSession, user: User) -> PartyMember | None:
    """The login's party member with places and volunteering loaded, read fresh."""
    return await session.scalar(
        select(PartyMember)
        .where(PartyMember.id == user.party_member_id)
        .options(
            joinedload(PartyMember.ward)
            .joinedload(Ward.constituency)
            .joinedload(Constituency.county),
            joinedload(PartyMember.registration_centre),
            selectinload(PartyMember.volunteer),
        )
        .execution_options(populate_existing=True)
    )


async def get_account_member(user: SignedInUser, session: SessionDep) -> PartyMember:
    """The approved member this login opens.

    Applies the party inbox first, so a queued withdrawal ends the session on this request.
    A member login whose member is no longer approved gets 401; any other login without an
    approved member gets 403.
    """
    if user.party_member_id is None:
        raise Forbidden("This login has no member account.")
    await membership.process_requests(session)
    member = await account_member(session, user)
    if member is None or not member.is_approved:
        if user.kind is UserKind.MEMBER:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your membership is not active.")
        raise Forbidden("This login has no member account.")
    return member


AccountMember = Annotated[PartyMember, Depends(get_account_member)]
