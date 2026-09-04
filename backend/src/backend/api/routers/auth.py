"""Signing in and out."""

from datetime import UTC, datetime

from fastapi import APIRouter, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select

from backend.api.deps import CurrentUser, SessionDep
from backend.models import AuthToken, User
from backend.schemas.auth import LoginRequest, LoginResponse
from backend.security import hash_password, needs_rehash, new_token_key, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

WRONG_CREDENTIALS = "Unable to log in with the provided credentials."


def _rejected() -> JSONResponse:
    """`non_field_errors` is what the sign-in form reads; `detail` is what everything else reads."""
    return JSONResponse(
        {"non_field_errors": [WRONG_CREDENTIALS], "detail": WRONG_CREDENTIALS},
        status_code=status.HTTP_400_BAD_REQUEST,
    )


@router.post("/login/", response_model=LoginResponse, responses={400: {"description": "Rejected"}})
async def login(payload: LoginRequest, session: SessionDep) -> object:
    """Exchange a username and password for the token every other route wants."""
    user = (
        await session.execute(select(User).where(User.username == payload.username))
    ).scalar_one_or_none()

    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.password_hash)
    ):
        return _rejected()

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)

    token = (
        await session.execute(select(AuthToken).where(AuthToken.user_id == user.id))
    ).scalar_one_or_none()
    if token is None:
        token = AuthToken(user_id=user.id, key=new_token_key())
        session.add(token)

    user.last_login_at = datetime.now(UTC)
    await session.commit()

    return {"token": token.key, "user": user}


@router.post("/logout/", status_code=status.HTTP_204_NO_CONTENT)
async def logout(user: CurrentUser, session: SessionDep) -> Response:
    """Delete the caller's token, so it stops working everywhere."""
    await session.execute(delete(AuthToken).where(AuthToken.user_id == user.id))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
