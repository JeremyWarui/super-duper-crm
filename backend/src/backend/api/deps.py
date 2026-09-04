"""Request dependencies: the session, the caller, and what their role may do."""

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.session import get_session
from backend.models import AuthToken, User, UserRole

SessionDep = Annotated[AsyncSession, Depends(get_session)]

# The scheme DRF used and the frontend still sends: "Authorization: Token <key>".
TOKEN_SCHEME = "Token"
_header = APIKeyHeader(name="Authorization", auto_error=False, scheme_name="Token")
AuthHeader = Annotated[str | None, Depends(_header)]

NOT_AUTHENTICATED = HTTPException(
    status.HTTP_401_UNAUTHORIZED,
    "Authentication credentials were not provided.",
    headers={"WWW-Authenticate": TOKEN_SCHEME},
)
INVALID_TOKEN = HTTPException(
    status.HTTP_401_UNAUTHORIZED,
    "Invalid token.",
    headers={"WWW-Authenticate": TOKEN_SCHEME},
)


def parse_token_header(header: str | None) -> str | None:
    """The key out of "Token <key>", or None when the header is absent or malformed."""
    if not header:
        return None
    scheme, _, key = header.partition(" ")
    if scheme != TOKEN_SCHEME or not key.strip():
        return None
    return key.strip()


async def get_optional_user(session: SessionDep, header: AuthHeader) -> User | None:
    """The caller, or None when they sent no token.

    A token that is present but unknown is an error, not an anonymous caller.
    """
    key = parse_token_header(header)
    if key is None:
        if header:
            raise INVALID_TOKEN
        return None
    result = await session.execute(
        select(AuthToken)
        .where(AuthToken.key == key)
        .options(
            selectinload(AuthToken.user).selectinload(User.mobilizer_profile),
        )
    )
    token = result.scalar_one_or_none()
    if token is None or not token.user.is_active:
        raise INVALID_TOKEN
    return token.user


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


async def get_current_user(user: OptionalUser) -> User:
    if user is None:
        raise NOT_AUTHENTICATED
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_writer(*, mobilizer_writable: bool = False):
    """Guard a write route. Managers always; mobilizers only where allowed.

    A candidate reads their campaign and never writes to it.
    """

    async def dependency(user: CurrentUser) -> User:
        if user.role is UserRole.MANAGER:
            return user
        if user.role is UserRole.MOBILIZER and mobilizer_writable:
            return user
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"A {user.role.label} may not change this.",
        )

    return dependency


def mobilizer_ward_id(user: User) -> uuid.UUID | None:
    """The one ward a mobilizer may see, or None for every other role.

    `User.mobilizer_profile` must be loaded; `get_optional_user` does that.
    A mobilizer with no profile row sees nothing, which the callers read as an
    empty result rather than an error.
    """
    if user.role is not UserRole.MOBILIZER:
        return None
    profile = user.mobilizer_profile
    return profile.ward_id if profile is not None else uuid.UUID(int=0)
