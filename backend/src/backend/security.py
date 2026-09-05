"""Password hashing and API token keys."""

import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from backend.config import get_settings

_hasher = PasswordHasher()

TOKEN_KEY_BYTES = 20

# Readable down a phone line once, worth nothing to a guesser.
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
    """A password for an account somebody else is creating.

    DEFAULT_USER_PASSWORD hands the same one to every account, so a demo has
    logins somebody can be told over the phone. Blank generates one per account.
    """
    return get_settings().default_user_password or secrets.token_urlsafe(PASSWORD_BYTES)
