"""Signing in and out; logins are created by the superuser."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import SessionDep, SignedInUser
from backend.api.routers.join import _client
from backend.models import AuthToken, User, UserKind
from backend.schemas.auth import LoginRequest, LoginResponse, LoginUser
from backend.security import hash_password, needs_rehash, new_token_key, verify_password
from backend.services.accounts import user_with_email
from backend.services.ratelimit import RateLimit

router = APIRouter(prefix="/auth", tags=["auth"])

WRONG_CREDENTIALS = "Unable to log in with the provided credentials."
TRIES = RateLimit(limit=10, window=3600)


async def _signed_in(session: AsyncSession, user: User) -> dict:
    """The login's token, created if it has none, and the login itself."""
    token = await session.scalar(select(AuthToken).where(AuthToken.user_id == user.id))
    if token is None:
        token = AuthToken(user_id=user.id, key=new_token_key())
        session.add(token)
    user.last_login_at = datetime.now(UTC)
    await session.commit()
    return {"token": token.key, "user": user}


@router.post(
    "/login/",
    response_model=LoginResponse,
    responses={400: {"description": "Rejected"}, 429: {"description": "Too many tries"}},
)
async def login(payload: LoginRequest, request: Request, session: SessionDep) -> object:
    """Exchange an email and password for a token; 10 tries an hour per device.

    A member login signs in only while its member is approved, and is refused otherwise with
    the answer a wrong password gets.
    """
    if not TRIES.allow(_client(request)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many tries; try later.")
    user = await user_with_email(session, payload.email, with_party_roles=True)
    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.password_hash)
        or (user.kind is UserKind.MEMBER and not user.member_account)
    ):
        # `non_field_errors` is what the sign-in form reads.
        return JSONResponse(
            {"non_field_errors": [WRONG_CREDENTIALS], "detail": WRONG_CREDENTIALS},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
    return await _signed_in(session, user)


@router.get("/me/", response_model=LoginUser)
async def me(user: SignedInUser) -> User:
    """The signed-in login, as the sign-in returns it."""
    return user


@router.post("/logout/", status_code=status.HTTP_204_NO_CONTENT)
async def logout(user: SignedInUser, session: SessionDep) -> Response:
    """Delete the caller's token everywhere."""
    await session.execute(delete(AuthToken).where(AuthToken.user_id == user.id))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
