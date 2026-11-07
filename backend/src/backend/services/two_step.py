"""2-step sign-in: TOTP codes from an authenticator app, and one-use recovery codes.

The superuser always needs it; staff logins need it when `staff_two_step_required` is on; anyone
else may turn it on. Once on, every password sign-in asks for a code.
"""

import base64
import hashlib
import secrets
import string
import time
from datetime import UTC, datetime

import pyotp
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models import AuthToken, SiteSettings, User, UserKind, UserTotp
from backend.services.audit import record
from backend.services.errors import Refused

ISSUER = "Campaign CRM"
RECOVERY_CODES = 10
STEP_SECONDS = 30
WRONG_CODE = "That code is not right. Use the newest code in your app, or a recovery code."
# Lowercase letters and digits, less the ones read as each other (i l o 0 1).
ALPHABET = "".join(c for c in string.ascii_lowercase + string.digits if c not in "ilo01")


def _fernet() -> Fernet:
    digest = hashlib.sha256(b"two-step:" + get_settings().secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _clean(code: str) -> str:
    return "".join(code.split()).replace("-", "").lower()


def _new_recovery_codes() -> list[str]:
    codes = []
    for _ in range(RECOVERY_CODES):
        raw = "".join(secrets.choice(ALPHABET) for _ in range(10))
        codes.append(f"{raw[:5]}-{raw[5:]}")
    return codes


async def row_of(session: AsyncSession, user: User) -> UserTotp | None:
    return await session.get(UserTotp, user.id)


async def is_on(session: AsyncSession, user: User) -> bool:
    """Whether this login's password sign-ins ask for a code."""
    row = await row_of(session, user)
    return row is not None and row.confirmed_at is not None


async def required(session: AsyncSession, user: User) -> bool:
    """Whether this login may work only after 2-step: the superuser, and staff when the switch
    is on."""
    if user.is_superuser:
        return True
    if user.kind is not UserKind.STAFF:
        return False
    return bool(await session.scalar(select(SiteSettings.staff_two_step_required)))


async def _locked(session: AsyncSession, user: User) -> UserTotp | None:
    """The row, locked until commit so two requests cannot spend the same code."""
    return await session.scalar(
        select(UserTotp)
        .where(UserTotp.user_id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def start(session: AsyncSession, user: User) -> tuple[str, str]:
    """A new secret for the app, and its otpauth link for the QR code; not on until confirmed."""
    row = await row_of(session, user)
    if row is not None and row.confirmed_at is not None:
        raise Refused("2-step sign-in is already on. Turn it off first to move it to a new app.")
    secret = pyotp.random_base32()
    encrypted = _fernet().encrypt(secret.encode()).decode()
    if row is None:
        session.add(UserTotp(user_id=user.id, secret=encrypted, last_step=0, recovery_hashes=[]))
    else:
        row.secret = encrypted
    await session.flush()
    name = user.email or user.username
    return secret, pyotp.TOTP(secret).provisioning_uri(name=name, issuer_name=ISSUER)


def _step_of(row: UserTotp, code: str) -> int | None:
    """The time step this 6-digit code is for (now, or one step either side), or None.

    A secret SECRET_KEY no longer opens matches nothing.
    """
    try:
        totp = pyotp.TOTP(_fernet().decrypt(row.secret.encode()).decode())
    except InvalidToken:
        return None
    now = int(time.time())
    for drift in (0, -1, 1):
        moment = now + drift * STEP_SECONDS
        if secrets.compare_digest(totp.at(moment), code):
            return moment // STEP_SECONDS
    return None


async def _take_app_code(session: AsyncSession, row: UserTotp, code: str) -> bool:
    """Spend an app code; only one request can move `last_step` past its step."""
    if not (len(code) == 6 and code.isascii() and code.isdigit()):
        return False
    step = _step_of(row, code)
    if step is None or step <= row.last_step:
        return False
    moved = await session.execute(
        update(UserTotp)
        .where(UserTotp.user_id == row.user_id, UserTotp.last_step < step)
        .values(last_step=step)
        .execution_options(synchronize_session=False)
    )
    if moved.rowcount != 1:
        return False
    row.last_step = step
    return True


async def confirm(session: AsyncSession, user: User, code: str) -> list[str]:
    """Turn 2-step on with the first code from the app; returns the recovery codes, shown once."""
    row = await _locked(session, user)
    if row is None or row.confirmed_at is not None:
        raise Refused("Start again: scan a new QR code first.")
    if not await _take_app_code(session, row, _clean(code)):
        raise Refused(WRONG_CODE)
    codes = _new_recovery_codes()
    row.recovery_hashes = [_hash(_clean(c)) for c in codes]
    row.confirmed_at = datetime.now(UTC)
    record(session, actor=user, action="two_step.on", subject_type="user", subject_id=user.id)
    await session.flush()
    return codes


async def check(session: AsyncSession, user: User, code: str) -> bool:
    """Whether the code passes 2-step for this login: an app code not used before, or an unused
    recovery code, which is then spent."""
    row = await _locked(session, user)
    if row is None or row.confirmed_at is None:
        return False
    code = _clean(code)
    if await _take_app_code(session, row, code):
        await session.flush()
        return True
    hashed = _hash(code)
    if hashed in row.recovery_hashes:
        row.recovery_hashes = [h for h in row.recovery_hashes if h != hashed]
        record(
            session,
            actor=user,
            action="two_step.recovery_used",
            subject_type="user",
            subject_id=user.id,
            detail={"left": len(row.recovery_hashes)},
        )
        await session.flush()
        return True
    return False


async def recovery_left(session: AsyncSession, user: User) -> int:
    row = await row_of(session, user)
    return len(row.recovery_hashes) if row is not None and row.confirmed_at else 0


async def renew_recovery(session: AsyncSession, user: User, code: str) -> list[str]:
    """New recovery codes for a current code; the old ones stop working."""
    if not await check(session, user, code):
        raise Refused(WRONG_CODE)
    row = await row_of(session, user)
    codes = _new_recovery_codes()
    row.recovery_hashes = [_hash(_clean(c)) for c in codes]
    record(
        session,
        actor=user,
        action="two_step.recovery_renewed",
        subject_type="user",
        subject_id=user.id,
    )
    await session.flush()
    return codes


async def turn_off(session: AsyncSession, user: User, code: str) -> None:
    """Turn 2-step off for a current code; refused while this login needs it."""
    if await required(session, user):
        raise Refused("Your login needs 2-step sign-in, so it stays on.")
    if not await check(session, user, code):
        raise Refused(WRONG_CODE)
    await session.delete(await row_of(session, user))
    record(session, actor=user, action="two_step.off", subject_type="user", subject_id=user.id)
    await session.flush()


async def reset(session: AsyncSession, user: User) -> None:
    """Take 2-step off a login that lost its app and codes, and sign it out everywhere."""
    row = await row_of(session, user)
    if row is not None:
        await session.delete(row)
    await session.execute(AuthToken.__table__.delete().where(AuthToken.user_id == user.id))
    record(session, actor=None, action="two_step.reset", subject_type="user", subject_id=user.id)
    await session.flush()
