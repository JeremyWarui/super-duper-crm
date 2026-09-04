"""Password hashing and API token keys."""

import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()

# Hex, so the key is safe in a header and in a URL. 40 characters.
TOKEN_KEY_BYTES = 20


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
    """True when the hash was made with weaker parameters than we use now."""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def new_token_key() -> str:
    return secrets.token_hex(TOKEN_KEY_BYTES)
