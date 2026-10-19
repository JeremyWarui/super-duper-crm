"""Password hashing and token keys, at the parameters production uses.

The rest of the suite hashes cheaply; this module opts back out.
"""

import pytest

from backend.security import (
    hash_password,
    new_token_key,
    verify_password,
)
from tests.factories import TEST_PASSWORD, fresh_password


@pytest.fixture(autouse=True)
def real_password_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    from argon2 import PasswordHasher

    monkeypatch.setattr("backend.security._hasher", PasswordHasher())


def test_the_hash_is_argon2id_and_hides_the_password() -> None:
    digest = hash_password(TEST_PASSWORD)
    assert digest.startswith("$argon2id$")
    assert TEST_PASSWORD not in digest


def test_the_right_password_verifies() -> None:
    assert verify_password(TEST_PASSWORD, hash_password(TEST_PASSWORD))


def test_the_wrong_password_does_not() -> None:
    assert not verify_password(fresh_password(), hash_password(TEST_PASSWORD))


def test_a_token_key_is_forty_hex_characters_and_unique() -> None:
    keys = {new_token_key() for _ in range(100)}
    assert len(keys) == 100
    assert all(len(k) == 40 and int(k, 16) >= 0 for k in keys)
