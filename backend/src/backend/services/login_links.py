"""One-time links that set a login's password: an invite for a new login, or a reset.

A link carries a random token; the database keeps only its SHA-256. A link works once, until it
expires, and issuing a new one of the same purpose voids the older ones.
"""

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import get_settings
from backend.models import LinkPurpose, LoginInvite, User, UserKind
from backend.security import hash_password, sha256_hex
from backend.services.accounts import new_login, sign_out, user_with_email
from backend.services.audit import record
from backend.services.clock import as_utc
from backend.services.email import send_email
from backend.services.errors import Refused

LIFETIME = {LinkPurpose.INVITE: timedelta(hours=72), LinkPurpose.RESET: timedelta(hours=1)}
PATH = {LinkPurpose.INVITE: "invite", LinkPurpose.RESET: "reset"}
SPENT = "This link has expired or was already used. Ask for a new one."
TOKEN_BYTES = 32


def may_sign_in(user: User) -> bool:
    """Whether the sign-in form would let this login in; needs `party_member` loaded."""
    if not user.is_active or user.pending:
        return False
    return user.kind is not UserKind.MEMBER or user.member_account


def link_url(purpose: LinkPurpose, token: str) -> str:
    return f"{get_settings().public_url.rstrip('/')}/{PATH[purpose]}/{token}"


async def issue(session: AsyncSession, user: User, purpose: LinkPurpose) -> str:
    """A new link token for the login, voiding its unused links of the same purpose."""
    now = datetime.now(UTC)
    await session.execute(
        update(LoginInvite)
        .where(
            LoginInvite.user_id == user.id,
            LoginInvite.purpose == purpose,
            LoginInvite.used_at.is_(None),
        )
        .values(used_at=now)
    )
    token = secrets.token_urlsafe(TOKEN_BYTES)
    session.add(
        LoginInvite(
            user_id=user.id,
            purpose=purpose,
            token_hash=sha256_hex(token),
            expires_at=now + LIFETIME[purpose],
        )
    )
    await session.flush()
    return token


def _wording(user: User, purpose: LinkPurpose, url: str) -> tuple[str, str]:
    name = user.first_name or user.username
    if purpose is LinkPurpose.INVITE:
        return (
            "Your sign-in is ready",
            f"Hello {name},\n\nA login has been made for you, username {user.username}. "
            f"Open this link within 72 hours to choose your password:\n\n{url}\n\n"
            "If you were not expecting this, ignore this email.",
        )
    return (
        "Reset your password",
        f"Hello {name},\n\nOpen this link within an hour to choose a new password:\n\n{url}\n\n"
        "If you did not ask for this, ignore this email; your password stays as it is.",
    )


async def send_link(session: AsyncSession, user: User, purpose: LinkPurpose) -> str:
    """Issue a link and email it; returns "email", or "none" when the login has no email."""
    if not user.email:
        return "none"
    token = await issue(session, user, purpose)
    subject, body = _wording(user, purpose, link_url(purpose, token))
    await send_email(session, user.email, subject, body, secret=token)
    return "email"


async def new_invited_login(session: AsyncSession, **details) -> tuple[User, str]:
    """Create a login with a password nobody knows, and email it an invite link.

    Returns the login and how the invite went out ("email", or "none" without an email).
    """
    user, _ = await new_login(session, password=secrets.token_urlsafe(TOKEN_BYTES), **details)
    return user, await send_link(session, user, LinkPurpose.INVITE)


async def _live(session: AsyncSession, token: str) -> tuple[LoginInvite, User]:
    link = await session.scalar(
        select(LoginInvite).where(LoginInvite.token_hash == sha256_hex(token))
    )
    if link is None or link.used_at is not None or as_utc(link.expires_at) <= datetime.now(UTC):
        raise Refused(SPENT)
    user = await session.scalar(
        select(User).where(User.id == link.user_id).options(selectinload(User.party_member))
    )
    if user is None or not may_sign_in(user):
        raise Refused(SPENT)
    return link, user


async def check(session: AsyncSession, token: str) -> tuple[LinkPurpose, User]:
    """What a live link is for and whose it is; refused when spent."""
    link, user = await _live(session, token)
    return link.purpose, user


async def claim(session: AsyncSession, token: str, password: str) -> User:
    """Set the login's password from a live link, spend it, and end the login's sessions."""
    link, user = await _live(session, token)
    now = datetime.now(UTC)
    # Spending this link first means two requests racing on it cannot both get through.
    spent = await session.execute(
        update(LoginInvite)
        .where(LoginInvite.id == link.id, LoginInvite.used_at.is_(None))
        .values(used_at=now)
    )
    if spent.rowcount != 1:
        raise Refused(SPENT)
    user.password_hash = hash_password(password)
    await session.execute(
        update(LoginInvite)
        .where(LoginInvite.user_id == user.id, LoginInvite.used_at.is_(None))
        .values(used_at=now)
    )
    await sign_out(session, user.id)
    record(
        session,
        actor=user,
        action=f"login.{link.purpose.value}_claimed",
        subject_type="user",
        subject_id=user.id,
    )
    await session.flush()
    return user


async def request_reset(session: AsyncSession, email: str) -> None:
    """Email a reset link when a login that may sign in has this address; silent either way."""
    user = await user_with_email(session, email)
    if user is not None and may_sign_in(user):
        await send_link(session, user, LinkPurpose.RESET)
    await session.commit()
