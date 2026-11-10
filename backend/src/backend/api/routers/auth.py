"""Signing in and out, Google sign-in, and the one-time links that set a password."""

import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated
from urllib.parse import urlencode

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.deps import SessionDep, SignedInUser
from backend.api.limits import TOO_MANY, check, client_key
from backend.config import get_settings
from backend.db.session import get_session_factory
from backend.models import AuthToken, User, UserKind
from backend.schemas.auth import (
    AuthOptions,
    GoogleFinish,
    LinkClaim,
    LinkRead,
    LoginRequest,
    LoginResponse,
    LoginUser,
    ResetRequest,
    ResetSent,
)
from backend.security import (
    hash_password,
    needs_rehash,
    new_token_key,
    sha256_hex,
    verify_password,
)
from backend.services import login_links, oidc
from backend.services.accounts import clean_email, sign_out, user_named, user_with_email
from backend.services.audit import record
from backend.services.clock import as_utc
from backend.services.ratelimit import RateLimit

router = APIRouter(prefix="/auth", tags=["auth"])

WRONG_CREDENTIALS = "Unable to log in with the provided credentials."
TRIES = RateLimit(limit=10, window=3600)
RESETS_PER_CLIENT = RateLimit(limit=5, window=3600)
RESETS_PER_ADDRESS = RateLimit(limit=3, window=3600)
CLAIMS = RateLimit(limit=20, window=3600)
RESET_SENT = "If that email has a login, a link to choose a new password is on its way."
GOOGLE_COOKIE = "google_sign_in"
GOOGLE_PATH = "/api/auth/google/"
HANDOFF_LIFE = timedelta(minutes=2)
HANDOFF_SPENT = "That Google sign-in has expired. Sign in again."


async def _signed_in(session: AsyncSession, user: User, *, handoff: str | None = None) -> dict:
    """The login's token, created if it has none, and the login itself. A `handoff` lets the
    browser fetch the token once."""
    token = await session.scalar(select(AuthToken).where(AuthToken.user_id == user.id))
    if token is None:
        token = AuthToken(user_id=user.id, key=new_token_key())
        session.add(token)
    if handoff is not None:
        token.handoff_hash = sha256_hex(handoff)
        token.handoff_expires_at = datetime.now(UTC) + HANDOFF_LIFE
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
    check(TRIES, request)
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
    await sign_out(session, user.id)
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
    if not RESETS_PER_CLIENT.allow(client_key(request)) or not RESETS_PER_ADDRESS.allow(email):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, TOO_MANY)
    background.add_task(_send_reset, opener, email)
    return ResetSent(detail=RESET_SENT)


@router.get("/links/{token}/", response_model=LinkRead)
async def read_link(token: str, request: Request, session: SessionDep) -> LinkRead:
    """What a live link is for and whose login it sets; 400 when it has expired or been used."""
    check(CLAIMS, request)
    purpose, user = await login_links.check(session, token)
    return LinkRead(purpose=purpose, username=user.username, email=user.email)


@router.post("/links/{token}/", response_model=LoginResponse)
async def claim_link(
    token: str, payload: LinkClaim, request: Request, session: SessionDep
) -> object:
    """Set the password from a live link and sign in; the link is spent."""
    check(CLAIMS, request)
    user = await login_links.claim(session, token, payload.password)
    signed = await user_named(session, user.username, with_party_roles=True)
    return await _signed_in(session, signed)


@router.get("/options/", response_model=AuthOptions)
async def options() -> AuthOptions:
    return AuthOptions(google=oidc.configured())


# Google sign-in: start sends the browser to Google, Google sends it back to the callback, and
# the callback sends it to /signin with a one-time handoff the page trades for the token.


def _to_signin(**query: str) -> RedirectResponse:
    target = f"{get_settings().public_url.rstrip('/')}/signin?{urlencode(query)}"
    response = RedirectResponse(target, status_code=status.HTTP_302_FOUND)
    response.delete_cookie(GOOGLE_COOKIE, path=GOOGLE_PATH)
    return response


def _need_google() -> None:
    if not oidc.configured():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Google sign-in is not set up here.")


@router.get("/google/start/", status_code=status.HTTP_302_FOUND)
async def google_start(
    bind: Annotated[str, Query(min_length=16, max_length=100, pattern=r"^[\w-]+$")],
) -> RedirectResponse:
    """Send the browser to Google, with the state, nonce and PKCE verifier kept in a 10-minute
    cookie. `bind` is a random value the page keeps; only it can finish this sign-in."""
    _need_google()
    state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
    try:
        url = await oidc.authorize_url(state, nonce, verifier)
    except (oidc.OidcError, OSError):
        return _to_signin(google_error="failed")
    response = RedirectResponse(url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        GOOGLE_COOKIE,
        f"{state}.{nonce}.{verifier}.{bind}",
        max_age=600,
        path=GOOGLE_PATH,
        httponly=True,
        samesite="lax",
        secure=get_settings().public_url.startswith("https://"),
    )
    return response


async def _google_refused(session: AsyncSession, reason: str, email: str = "") -> RedirectResponse:
    record(
        session,
        actor=None,
        actor_name="google",
        action="login.google_refused",
        subject_type="user",
        detail={"reason": reason, "email": email},
    )
    await session.commit()
    return _to_signin(google_error=reason)


@router.get("/google/callback/", status_code=status.HTTP_302_FOUND)
async def google_callback(
    request: Request, session: SessionDep, code: str = "", state: str = "", error: str = ""
) -> RedirectResponse:
    """Check Google's answer and sign in the existing login with that verified email.

    Never creates a login. Every outcome is audited; a refusal names its reason in
    `google_error`: cancelled, expired, failed, unverified or unknown.
    """
    _need_google()
    if not CLAIMS.allow(client_key(request)):
        return await _google_refused(session, "busy")
    saved = request.cookies.get(GOOGLE_COOKIE, "").split(".")
    expected, nonce, verifier, bind = saved if len(saved) == 4 and all(saved) else ("",) * 4
    if error:
        return await _google_refused(session, "cancelled")
    if not (expected and code and secrets.compare_digest(state.encode(), expected.encode())):
        return await _google_refused(session, "expired")
    try:
        found = await oidc.identity(code, nonce, verifier)
    except (oidc.OidcError, OSError):
        return await _google_refused(session, "failed")
    email = clean_email(found.email)
    if not email or not found.email_verified:
        return await _google_refused(session, "unverified", email)
    user = await user_with_email(session, email, with_party_roles=True)
    if user is None or not login_links.may_sign_in(user):
        return await _google_refused(session, "unknown", email)
    handoff = secrets.token_urlsafe(32)
    record(session, actor=user, action="login.google", subject_type="user", subject_id=user.id)
    await _signed_in(session, user, handoff=f"{handoff}:{bind}")
    return _to_signin(google=handoff)


@router.post(
    "/google/finish/",
    response_model=LoginResponse,
    responses={400: {"description": "Spent"}, 429: {"description": "Too many tries"}},
)
async def google_finish(payload: GoogleFinish, request: Request, session: SessionDep) -> object:
    """Trade the callback's handoff for the session, once, within two minutes, from the page
    holding the `bind` value the sign-in started with."""
    check(CLAIMS, request)
    hashed = sha256_hex(f"{payload.handoff}:{payload.bind}")
    token = await session.scalar(select(AuthToken).where(AuthToken.handoff_hash == hashed))
    expires = as_utc(token.handoff_expires_at) if token and token.handoff_expires_at else None
    if token is None or expires is None or expires <= datetime.now(UTC):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, HANDOFF_SPENT)
    spent = await session.execute(
        update(AuthToken)
        .where(AuthToken.id == token.id, AuthToken.handoff_hash == hashed)
        .values(handoff_hash=None, handoff_expires_at=None)
    )
    if spent.rowcount != 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, HANDOFF_SPENT)
    user = await session.scalar(
        select(User)
        .where(User.id == token.user_id)
        .options(selectinload(User.party_roles), selectinload(User.party_member))
    )
    await session.commit()
    return {"token": token.key, "user": user}
