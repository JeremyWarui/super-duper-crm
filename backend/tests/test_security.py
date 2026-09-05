"""Password hashing and token keys, at the parameters production uses.

The rest of the suite hashes cheaply; this module opts back out.
"""

from collections.abc import Iterator

import pytest

from backend.config import get_settings
from backend.security import (
    hash_password,
    needs_rehash,
    new_password,
    new_token_key,
    verify_password,
)
from tests.factories import TEST_PASSWORD


@pytest.fixture(autouse=True)
def real_password_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    from argon2 import PasswordHasher

    monkeypatch.setattr("backend.security._hasher", PasswordHasher())


def test_the_hash_is_argon2id_and_hides_the_password() -> None:
    digest = hash_password(TEST_PASSWORD)
    assert digest.startswith("$argon2id$")
    assert TEST_PASSWORD not in digest


def test_the_hash_fits_the_column() -> None:
    """User.password_hash is VARCHAR(128); a longer hash would be truncated."""
    from backend.models import User

    assert len(hash_password(TEST_PASSWORD)) <= User.__table__.c.password_hash.type.length


def test_the_same_password_hashes_differently_each_time() -> None:
    assert hash_password("same") != hash_password("same")


def test_the_right_password_verifies() -> None:
    assert verify_password(TEST_PASSWORD, hash_password(TEST_PASSWORD))


def test_the_wrong_password_does_not() -> None:
    assert not verify_password("wrong", hash_password(TEST_PASSWORD))


def test_an_empty_stored_hash_rejects_every_password() -> None:
    assert not verify_password("", "")
    assert not verify_password("anything", "")


def test_a_corrupt_stored_hash_rejects_rather_than_raising() -> None:
    assert not verify_password("anything", "not-a-hash")


def test_a_fresh_hash_does_not_need_rehashing() -> None:
    assert not needs_rehash(hash_password(TEST_PASSWORD))


def test_a_hash_from_weaker_parameters_needs_rehashing() -> None:
    weak = "$argon2id$v=19$m=8,t=1,p=1$c29tZXNhbHRzb21lc2E$Xpj4Zk1CVSC8Ck0zVUJb1w"
    assert needs_rehash(weak)


def test_an_unreadable_hash_counts_as_needing_a_rehash() -> None:
    assert needs_rehash("not-a-hash")


def test_a_token_key_is_forty_hex_characters_and_unique() -> None:
    keys = {new_token_key() for _ in range(100)}
    assert len(keys) == 100
    assert all(len(k) == 40 and int(k, 16) >= 0 for k in keys)


# ------------------------------------------------- the password a route hands out


@pytest.fixture
def fresh_settings() -> Iterator[None]:
    """Read the environment again, either side of the test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_a_blank_default_generates_a_different_password_each_time(
    monkeypatch: pytest.MonkeyPatch, fresh_settings: None
) -> None:
    monkeypatch.setenv("DEFAULT_USER_PASSWORD", "")
    get_settings.cache_clear()
    assert len({new_password() for _ in range(20)}) == 20


def test_the_default_password_is_handed_to_every_account(
    monkeypatch: pytest.MonkeyPatch, fresh_settings: None
) -> None:
    """DEFAULT_USER_PASSWORD gives a demo logins somebody can be told."""
    monkeypatch.setenv("DEFAULT_USER_PASSWORD", "campaign1234")
    get_settings.cache_clear()
    assert {new_password() for _ in range(5)} == {"campaign1234"}


def test_the_default_password_still_hashes_and_verifies(
    monkeypatch: pytest.MonkeyPatch, fresh_settings: None
) -> None:
    monkeypatch.setenv("DEFAULT_USER_PASSWORD", "campaign1234")
    get_settings.cache_clear()
    digest = hash_password(new_password())
    assert verify_password("campaign1234", digest)
    assert not verify_password("campaign1235", digest)
