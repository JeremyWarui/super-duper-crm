"""The migrations build the schema the models describe, on SQLite and as Postgres SQL."""

import functools
import secrets
from urllib.parse import quote

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations

from backend.config import alembic_url, get_settings
from backend.models import Base
from tests.conftest import revision_modules, upgrade_head


@pytest.fixture
def migrated_metadata() -> sa.MetaData:
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        upgrade_head(connection)
        reflected = sa.MetaData()
        reflected.reflect(bind=connection)
    engine.dispose()
    return reflected


def test_revisions_form_a_single_chain() -> None:
    revisions = revision_modules()
    assert len([m for m in revisions if m.down_revision is None]) == 1
    parents = [m.down_revision for m in revisions if m.down_revision is not None]
    assert set(parents) <= {m.revision for m in revisions}
    assert len(parents) == len(set(parents)), "two revisions share a parent"


def test_the_migrated_tables_and_columns_match_the_models(migrated_metadata: sa.MetaData) -> None:
    assert set(migrated_metadata.tables) == set(Base.metadata.tables)
    for name, model_table in Base.metadata.tables.items():
        migrated = {c.name: c.nullable for c in migrated_metadata.tables[name].columns}
        assert migrated == {c.name: c.nullable for c in model_table.columns}, name


def test_the_migrated_indexes_match_the_models(migrated_metadata: sa.MetaData) -> None:
    for name, model_table in Base.metadata.tables.items():
        migrated = {i.name for i in migrated_metadata.tables[name].indexes}
        assert {i.name for i in model_table.indexes} <= migrated, name


def test_the_migrated_foreign_keys_delete_as_the_models_say(
    migrated_metadata: sa.MetaData,
) -> None:
    def rules(table: sa.Table) -> set[tuple[str, str, str | None]]:
        return {
            (fk.parent.name, fk.column.table.name, fk.ondelete and fk.ondelete.upper())
            for fk in table.foreign_keys
        }

    for name, model_table in Base.metadata.tables.items():
        assert rules(migrated_metadata.tables[name]) == rules(model_table), name


def test_downgrade_removes_every_table() -> None:
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        revisions = revision_modules()
        with Operations.context(MigrationContext.configure(connection)):
            for module in revisions:
                module.upgrade()
            for module in reversed(revisions):
                module.downgrade()
        left_over = sa.MetaData()
        left_over.reflect(bind=connection)
    engine.dispose()
    assert set(left_over.tables) == set()


@functools.cache
def _postgres_sql() -> str:
    """The migrations rendered as Postgres SQL, without a database."""
    import io
    import os
    from contextlib import redirect_stdout
    from pathlib import Path

    from alembic import command

    root = Path(__file__).resolve().parent.parent
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://USER:PASSWORD@localhost:5432/campaign_crm"
    get_settings.cache_clear()
    try:
        config = Config(str(root / "alembic.ini"))
        config.set_main_option("script_location", str(root / "alembic"))
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            command.upgrade(config, "head", sql=True)
        return buffer.getvalue()
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        get_settings.cache_clear()


def test_the_migrations_render_as_postgres_with_every_table() -> None:
    sql = _postgres_sql()
    assert sql.strip().startswith("BEGIN;")
    assert sql.strip().endswith("COMMIT;")
    for table in Base.metadata.tables:
        assert f"CREATE TABLE {table}" in sql, table
    assert "ON DELETE CASCADE" in sql
    assert "ON DELETE SET NULL" in sql


def test_the_unique_indexes_keep_their_where_clause_in_postgres() -> None:
    sql = _postgres_sql()
    assert (
        "CREATE UNIQUE INDEX uq_targets_campaign_ward ON targets "
        "(campaign_id, ward_id) WHERE registration_centre_id IS NULL" in sql
    )
    assert (
        "CREATE UNIQUE INDEX uq_targets_campaign_registration_centre ON targets "
        "(campaign_id, registration_centre_id) WHERE registration_centre_id IS NOT NULL" in sql
    )
    assert (
        "CREATE UNIQUE INDEX uq_campaign_members_one_candidate ON campaign_members "
        "(campaign_id) WHERE role = 'candidate'" in sql
    )
    assert (
        "CREATE UNIQUE INDEX uq_campaign_members_one_campaign_per_user ON campaign_members "
        "(user_id)" in sql
    )


def test_a_password_with_a_percent_survives_the_alembic_config(
    monkeypatch: pytest.MonkeyPatch, fresh_settings: None
) -> None:
    """A percent-encoded `@` in the password must not trip configparser interpolation."""
    with_an_at = f"{secrets.token_hex(4)}@{secrets.token_hex(4)}"
    dsn = f"postgresql+asyncpg://postgres:{quote(with_an_at, safe='')}@localhost:5432/campaign_crm"
    monkeypatch.setenv("DATABASE_URL", dsn)
    get_settings.cache_clear()
    config = Config()
    config.set_main_option("sqlalchemy.url", alembic_url())
    assert config.get_main_option("sqlalchemy.url") == dsn
