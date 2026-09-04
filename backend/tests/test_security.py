"""Password hashing and token keys."""

from backend.security import (
    hash_password,
    needs_rehash,
    new_token_key,
    verify_password,
)


def test_the_hash_is_argon2id_and_hides_the_password() -> None:
    digest = hash_password("correct-horse-battery")
    assert digest.startswith("$argon2id$")
    assert "correct-horse-battery" not in digest


def test_the_hash_fits_the_column() -> None:
    """User.password_hash is VARCHAR(128); a longer hash would be truncated."""
    from backend.models import User

    assert len(hash_password("correct-horse-battery")) <= User.__table__.c.password_hash.type.length


def test_the_same_password_hashes_differently_each_time() -> None:
    """Each hash carries its own salt, so equal passwords are not equal rows."""
    assert hash_password("same") != hash_password("same")


def test_the_right_password_verifies() -> None:
    assert verify_password("correct-horse-battery", hash_password("correct-horse-battery"))


def test_the_wrong_password_does_not() -> None:
    assert not verify_password("wrong", hash_password("correct-horse-battery"))


def test_an_empty_stored_hash_rejects_every_password() -> None:
    """A user created without a password cannot be signed in as."""
    assert not verify_password("", "")
    assert not verify_password("anything", "")


def test_a_corrupt_stored_hash_rejects_rather_than_raising() -> None:
    assert not verify_password("anything", "not-a-hash")


def test_a_fresh_hash_does_not_need_rehashing() -> None:
    assert not needs_rehash(hash_password("correct-horse-battery"))


def test_a_hash_from_weaker_parameters_needs_rehashing() -> None:
    weak = "$argon2id$v=19$m=8,t=1,p=1$c29tZXNhbHRzb21lc2E$Xpj4Zk1CVSC8Ck0zVUJb1w"
    assert needs_rehash(weak)


def test_an_unreadable_hash_counts_as_needing_a_rehash() -> None:
    assert needs_rehash("not-a-hash")


def test_a_token_key_is_forty_hex_characters_and_unique() -> None:
    keys = {new_token_key() for _ in range(100)}
    assert len(keys) == 100
    assert all(len(k) == 40 and int(k, 16) >= 0 for k in keys)
