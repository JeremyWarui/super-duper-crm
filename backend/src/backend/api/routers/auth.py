"""Signing up, in, and out."""

from datetime import UTC, datetime

from fastapi import APIRouter, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import CurrentUser, SessionDep
from backend.models import AuthToken, User
from backend.schemas.auth import LoginRequest, LoginResponse, RegisterRequest
from backend.security import hash_password, needs_rehash, new_token_key, verify_password
from backend.services.accounts import new_login, user_named

router = APIRouter(prefix="/auth", tags=["auth"])

WRONG_CREDENTIALS = "Unable to log in with the provided credentials."


async def _signed_in(session: AsyncSession, user: User) -> dict:
    """The login's token, created if it has none, and the login itself."""
    token = await session.scalar(select(AuthToken).where(AuthToken.user_id == user.id))
    if token is None:
        token = AuthToken(user_id=user.id, key=new_token_key())
        session.add(token)
    user.last_login_at = datetime.now(UTC)
    await session.commit()
    return {"token": token.key, "user": user}


@router.post("/login/", response_model=LoginResponse, responses={400: {"description": "Rejected"}})
async def login(payload: LoginRequest, session: SessionDep) -> object:
    """Exchange a username and password for a token."""
    user = await user_named(session, payload.username)
    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.password_hash)
    ):
        # `non_field_errors` is what the sign-in form reads.
        return JSONResponse(
            {"non_field_errors": [WRONG_CREDENTIALS], "detail": WRONG_CREDENTIALS},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
    return await _signed_in(session, user)


@router.post(
    "/register/",
    response_model=LoginResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"description": "Username taken"}},
)
async def register(payload: RegisterRequest, session: SessionDep) -> object:
    """Create a candidate or manager login and sign it in."""
    user, _ = await new_login(session, **payload.model_dump())
    return await _signed_in(session, user)


@router.post("/logout/", status_code=status.HTTP_204_NO_CONTENT)
async def logout(user: CurrentUser, session: SessionDep) -> Response:
    """Delete the caller's token everywhere."""
    await session.execute(delete(AuthToken).where(AuthToken.user_id == user.id))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
