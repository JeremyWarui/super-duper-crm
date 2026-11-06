"""Signing in and out, and the one-time links that set a password."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import SessionDep, SignedInUser
from backend.api.routers.join import _client
from backend.db.session import get_session_factory
from backend.models import AuthToken, User, UserKind
from backend.schemas.auth import (
    LinkClaim,
    LinkRead,
    LoginRequest,
    LoginResponse,
    LoginUser,
    ResetRequest,
    ResetSent,
)
from backend.security import hash_password, needs_rehash, new_token_key, verify_password
from backend.services import login_links
from backend.services.accounts import clean_email, user_named, user_with_email
from backend.services.ratelimit import RateLimit

router = APIRouter(prefix="/auth", tags=["auth"])

WRONG_CREDENTIALS = "Unable to log in with the provided credentials."
TRIES = RateLimit(limit=10, window=3600)
RESETS_PER_CLIENT = RateLimit(limit=5, window=3600)
RESETS_PER_ADDRESS = RateLimit(limit=3, window=3600)
CLAIMS = RateLimit(limit=20, window=3600)
RESET_SENT = "If that email has a login, a link to choose a new password is on its way."


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


async def _send_reset(opener, email: str) -> None:
    async with opener() as session:
        await login_links.request_reset(session, email)


@router.post(
    "/password-reset/",
    response_model=ResetSent,
    responses={429: {"description": "Too many tries"}},
)
async def request_reset(
    payload: ResetRequest,
    request: Request,
    background: BackgroundTasks,
    opener: Annotated[Callable, Depends(get_session_factory)],
) -> ResetSent:
    """Email a reset link to the login with this address, if there is one.

    The reply is the same either way, and the email goes out after it, so neither the answer nor
    its timing says whether the address has a login. 5 requests an hour per device, 3 per address.
    """
    email = clean_email(payload.email)
    if not RESETS_PER_CLIENT.allow(_client(request)) or not RESETS_PER_ADDRESS.allow(email):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many tries; try later.")
    background.add_task(_send_reset, opener, email)
    return ResetSent(detail=RESET_SENT)


@router.get("/links/{token}/", response_model=LinkRead)
async def read_link(token: str, request: Request, session: SessionDep) -> LinkRead:
    """What a live link is for and whose login it sets; 400 when it has expired or been used."""
    if not CLAIMS.allow(_client(request)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many tries; try later.")
    purpose, user = await login_links.check(session, token)
    return LinkRead(purpose=purpose, username=user.username, email=user.email)


@router.post("/links/{token}/", response_model=LoginResponse)
async def claim_link(
    token: str, payload: LinkClaim, request: Request, session: SessionDep
) -> object:
    """Set the password from a live link and sign in; the link is spent."""
    if not CLAIMS.allow(_client(request)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many tries; try later.")
    user = await login_links.claim(session, token, payload.password)
    signed = await user_named(session, user.username, with_party_roles=True)
    return await _signed_in(session, signed)
