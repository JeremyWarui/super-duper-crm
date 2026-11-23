"""Request dependencies: the session, the signed-in caller, and role guards."""

import re
from datetime import date
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.session import get_session
from backend.models import AuthToken, User
from backend.services import access, clock, permissions, site
from backend.services.errors import Forbidden

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
        .options(selectinload(AuthToken.user).selectinload(User.mobilizer_profile))
    )
    if token is None or not token.user.is_active:
        raise _unauthorized("Invalid token.")
    return token.user


SignedInUser = Annotated[User, Depends(get_signed_in_user)]


async def get_today() -> date:
    return clock.today()


Today = Annotated[date, Depends(get_today)]


async def get_set_up(session: SessionDep) -> bool:
    """Whether setup has run."""
    return await site.is_set_up(session)


# What a closed campaign's team may still change: their sign-out, and the data protection work.
OPEN_WHEN_CLOSED = re.compile(r"^/api/(auth/|campaigns/[0-9a-f-]+/data/)")


async def get_current_user(user: SignedInUser, session: SessionDep, request: Request) -> User:
    """The signed-in caller; a closed campaign's team may only read (`services/access.py`)."""
    if user.role is None or user.is_superuser:
        return user
    found = await access.login_access(session, user.id)
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


AdminUser = Annotated[User, Depends(require_superuser)]
