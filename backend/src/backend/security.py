"""Password hashing, API token keys, and the random codes and digests the app hands out."""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from backend.config import get_settings

_hasher = PasswordHasher()

TOKEN_KEY_BYTES = 20

PASSWORD_BYTES = 9


def hash_password(password: str) -> str:
    """Argon2id hash, salt included."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """False for a wrong password, a malformed hash, or no hash at all."""
    if not password_hash:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True when the hash uses weaker parameters than the current ones."""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def new_token_key() -> str:
    return secrets.token_hex(TOKEN_KEY_BYTES)


def new_password() -> str:
    """DEFAULT_USER_PASSWORD when set, otherwise a generated one."""
    return get_settings().default_user_password or secrets.token_urlsafe(PASSWORD_BYTES)


def new_withdraw_code() -> str:
    """The private code a person withdraws their own sign-up with."""
    return secrets.token_urlsafe(18)


def new_short_code() -> str:
    """A 12-character code for a link people share, such as a sign-up or team link."""
    return secrets.token_urlsafe(9)


def sha256_hex(value: str | bytes) -> str:
    """The SHA-256 of `value` as 64 hex characters; text is hashed as UTF-8."""
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()
