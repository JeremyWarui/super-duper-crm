"""A login is held to one campaign by the database, from revision f6a7b8c9d0e1 on.

Each test builds a real database with the migrations, stopped just before the
index, so the rows it meets are the ones an existing deployment holds.
"""

import importlib.util
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError

VERSIONS = sorted((Path(__file__).resolve().parent.parent / "alembic" / "versions").glob("*.py"))
ONE_CAMPAIGN = "f6a7b8c9d0e1"


def _load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _in_order():
    return [_load(path) for path in VERSIONS]


def _run(db, modules, step="upgrade"):
    engine = sa.create_engine(f"sqlite:///{db.as_posix()}")
    try:
        with (
            engine.begin() as connection,
            Operations.context(MigrationContext.configure(connection)),
        ):
            for module in modules:
                getattr(module, step)()
    finally:
        engine.dispose()


def _sql(db, statement, **params):
    engine = sa.create_engine(f"sqlite:///{db.as_posix()}")
    try:
        with engine.begin() as connection:
            result = connection.execute(sa.text(statement), params)
            return result.all() if result.returns_rows else None
    finally:
        engine.dispose()


def _user(db, username, role):
    user_id = uuid.uuid4().hex
    _sql(
        db,
        "INSERT INTO users (id, username, email, first_name, last_name, phone, role, "
        "password_hash, is_active, is_superuser, created_at) "
        "VALUES (:id, :username, '', '', '', '', :role, 'x', 1, 0, CURRENT_TIMESTAMP)",
        id=user_id,
        username=username,
        role=role,
    )
    return user_id


def _campaign(db, title):
    campaign_id = uuid.uuid4().hex
    _sql(
        db,
        "INSERT INTO campaigns (id, title, office_level, created_at) "
        "VALUES (:id, :title, 'ward', CURRENT_TIMESTAMP)",
        id=campaign_id,
        title=title,
    )
    return campaign_id


def _member(db, campaign_id, user_id, role):
    _sql(
        db,
        "INSERT INTO campaign_members (id, campaign_id, user_id, role, created_at) "
        "VALUES (:id, :campaign, :user, :role, CURRENT_TIMESTAMP)",
        id=uuid.uuid4().hex,
        campaign=campaign_id,
        user=user_id,
        role=role,
    )


@pytest.fixture
def before(tmp_path):
    """A database migrated to just before the index."""
    db = tmp_path / "before.sqlite3"
    modules = _in_order()
    upto = [m for m in modules if m.revision != ONE_CAMPAIGN]
    assert len(upto) == len(modules) - 1, "the revision under test is not in the chain"
    _run(db, upto)
    return db


def _index():
    return next(m for m in _in_order() if m.revision == ONE_CAMPAIGN)


def test_a_login_on_two_campaigns_stops_the_upgrade_and_is_named_with_both(before) -> None:
    amina = _user(before, "amina", "manager")
    _member(before, _campaign(before, "Jane for Zimmerman"), amina, "manager")
    _member(before, _campaign(before, "Peter for Githurai"), amina, "manager")

    with pytest.raises(RuntimeError, match=r"amina \(Jane for Zimmerman, Peter for Githurai\)"):
        _run(before, [_index()])

    indexes = {row[1] for row in _sql(before, "PRAGMA index_list(campaign_members)")}
    assert "uq_campaign_members_one_campaign_per_user" not in indexes


def test_a_deployment_where_everyone_is_on_one_campaign_upgrades(before) -> None:
    jane = _user(before, "jane", "candidate")
    amina = _user(before, "amina", "manager")
    campaign = _campaign(before, "Jane for Zimmerman")
    _member(before, campaign, jane, "candidate")
    _member(before, campaign, amina, "manager")

    _run(before, [_index()])

    indexes = {row[1] for row in _sql(before, "PRAGMA index_list(campaign_members)")}
    assert "uq_campaign_members_one_campaign_per_user" in indexes


def test_after_the_upgrade_the_database_refuses_a_second_campaign(before) -> None:
    amina = _user(before, "amina", "manager")
    _member(before, _campaign(before, "Jane for Zimmerman"), amina, "manager")
    _run(before, [_index()])

    with pytest.raises(IntegrityError):
        _member(before, _campaign(before, "Peter for Githurai"), amina, "manager")


def test_downgrade_lets_a_login_onto_two_campaigns_again(before) -> None:
    _run(before, [_index()])
    _run(before, [_index()], step="downgrade")
    amina = _user(before, "amina", "manager")

    _member(before, _campaign(before, "Jane for Zimmerman"), amina, "manager")
    _member(before, _campaign(before, "Peter for Githurai"), amina, "manager")

    rows = _sql(before, "SELECT COUNT(*) FROM campaign_members WHERE user_id = :u", u=amina)
    assert rows[0][0] == 2
