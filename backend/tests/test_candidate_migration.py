"""The candidate moves out of `campaigns.candidate_id` and into `campaign_members` alone.

Each test builds a real database with the migrations, stopped just before the
move, so the rows the move meets are the ones an existing deployment holds.
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
CHECK = "d4e5f6a7b8c9"
DROP = "e5f6a7b8c9d0"


def _load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _in_order():
    return [_load(path) for path in VERSIONS]


def _engine(db):
    return sa.create_engine(f"sqlite:///{db.as_posix()}")


def _migrate(db, *, until):
    """Every revision in order, stopping before `until`."""
    engine = _engine(db)
    try:
        with (
            engine.begin() as connection,
            Operations.context(MigrationContext.configure(connection)),
        ):
            for module in _in_order():
                if module.revision == until:
                    break
                module.upgrade()
    finally:
        engine.dispose()


def _run(db, revision, step="upgrade"):
    module = next(m for m in _in_order() if m.revision == revision)
    engine = _engine(db)
    try:
        with (
            engine.begin() as connection,
            Operations.context(MigrationContext.configure(connection)),
        ):
            getattr(module, step)()
    finally:
        engine.dispose()


def _sql(db, statement, **params):
    engine = _engine(db)
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


def _campaign(db, title, candidate_id):
    campaign_id = uuid.uuid4().hex
    _sql(
        db,
        "INSERT INTO campaigns (id, candidate_id, title, office_level, created_at) "
        "VALUES (:id, :candidate, :title, 'ward', CURRENT_TIMESTAMP)",
        id=campaign_id,
        candidate=candidate_id,
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


def _candidates(db, campaign_id):
    rows = _sql(
        db,
        "SELECT user_id FROM campaign_members WHERE campaign_id = :c AND role = 'candidate'",
        c=campaign_id,
    )
    return [row[0] for row in rows]


def _columns(db, table):
    return {row[1] for row in _sql(db, f"PRAGMA table_info({table})")}


@pytest.fixture
def before(tmp_path):
    """A database migrated to just before the candidate moves."""
    db = tmp_path / "before.sqlite3"
    _migrate(db, until=CHECK)
    return db


def _moved(db, title="Jane for Zimmerman"):
    """One campaign, its candidate on it, and the move applied."""
    jane = _user(db, "jane", "candidate")
    campaign = _campaign(db, title, jane)
    _member(db, campaign, jane, "candidate")
    _run(db, CHECK)
    _run(db, DROP)
    return campaign, jane


def test_every_campaign_keeps_its_candidate_when_the_column_goes(before) -> None:
    campaign, jane = _moved(before)

    assert "candidate_id" not in _columns(before, "campaigns")
    assert _candidates(before, campaign) == [jane]


def test_a_missing_candidate_row_is_filled_in_from_the_column(before) -> None:
    jane = _user(before, "jane", "candidate")
    campaign = _campaign(before, "Jane for Zimmerman", jane)

    _run(before, CHECK)

    assert _candidates(before, campaign) == [jane]


def test_two_candidate_rows_stop_the_upgrade_and_name_the_campaign(before) -> None:
    jane = _user(before, "jane", "candidate")
    peter = _user(before, "peter", "candidate")
    campaign = _campaign(before, "Jane for Zimmerman", jane)
    _member(before, campaign, jane, "candidate")
    _member(before, campaign, peter, "candidate")

    with pytest.raises(RuntimeError, match="Jane for Zimmerman"):
        _run(before, CHECK)

    assert "candidate_id" in _columns(before, "campaigns")


def test_a_candidate_row_for_somebody_else_stops_the_upgrade(before) -> None:
    """One row, but not the person the column names; which is right is a person's call."""
    boss = _user(before, "boss", "manager")
    peter = _user(before, "peter", "candidate")
    campaign = _campaign(before, "Boss for Zimmerman", boss)
    _member(before, campaign, peter, "candidate")

    with pytest.raises(RuntimeError, match="Boss for Zimmerman"):
        _run(before, CHECK)


def test_a_campaign_with_no_candidate_at_all_stops_the_upgrade(before) -> None:
    boss = _user(before, "boss", "manager")
    _campaign(before, "Nobody For Zimmerman", boss)

    with pytest.raises(RuntimeError, match="Nobody For Zimmerman"):
        _run(before, CHECK)


def test_after_the_move_a_campaign_cannot_hold_a_second_candidate(before) -> None:
    campaign, _jane = _moved(before)
    peter = _user(before, "peter", "candidate")

    with pytest.raises(IntegrityError):
        _member(before, campaign, peter, "candidate")


def test_after_the_move_a_campaign_may_still_hold_many_managers(before) -> None:
    campaign, _jane = _moved(before)

    for name in ("amina", "otieno"):
        _member(before, campaign, _user(before, name, "manager"), "manager")

    rows = _sql(before, "SELECT 1 FROM campaign_members WHERE campaign_id = :c", c=campaign)
    assert len(rows) == 3


def test_the_rebuilt_table_still_refuses_an_office_that_does_not_exist(before) -> None:
    """SQLite rebuilds campaigns to drop the column; its CHECK has to come back with it."""
    _moved(before)

    with pytest.raises(IntegrityError):
        _sql(
            before,
            "INSERT INTO campaigns (id, title, office_level, created_at) "
            "VALUES (:id, 'Bad', 'president', CURRENT_TIMESTAMP)",
            id=uuid.uuid4().hex,
        )


def test_downgrading_puts_the_column_back_from_the_members(before) -> None:
    campaign, jane = _moved(before)

    _run(before, DROP, "downgrade")

    assert "candidate_id" in _columns(before, "campaigns")
    assert _sql(before, "SELECT candidate_id FROM campaigns WHERE id = :c", c=campaign) == [(jane,)]
