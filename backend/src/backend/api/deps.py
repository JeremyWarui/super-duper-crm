"""Request dependencies: the session, the signed-in caller, and role guards."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.session import get_session
from backend.models import AuthToken, User, UserRole

SessionDep = Annotated[AsyncSession, Depends(get_session)]

TOKEN_SCHEME = "Token"
_header = APIKeyHeader(name="Authorization", auto_error=False, scheme_name="Token")


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": TOKEN_SCHEME}
    )


async def get_current_user(
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


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: UserRole, message: str | None = None):
    """A guard letting only these roles through; 403 otherwise."""

    async def dependency(user: CurrentUser) -> User:
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


AdminUser = Annotated[User, Depends(require_superuser)]
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
