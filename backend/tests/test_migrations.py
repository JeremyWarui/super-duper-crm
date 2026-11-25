"""The migrations build the schema the models describe, on SQLite and as Postgres SQL."""

import contextlib
import functools
import secrets
import uuid
from collections.abc import AsyncIterator
from urllib.parse import quote

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.config import alembic_url, get_settings
from backend.models import Base
from tests.conftest import POSTGRES, postgres_url, revision_modules, upgrade_head


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


def _down_and_up(connection) -> None:
    with Operations.context(MigrationContext.configure(connection)):
        for module in reversed(revision_modules()):
            module.downgrade()
        for module in revision_modules():
            module.upgrade()


@contextlib.asynccontextmanager
async def _scratch_postgres(suffix: str) -> AsyncIterator[AsyncEngine]:
    """An empty database on the local Postgres, dropped afterwards."""
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import create_async_engine

    name = f"{make_url(postgres_url()).database}_{suffix}"
    admin = create_async_engine(postgres_url("postgres"), isolation_level="AUTOCOMMIT")
    async with admin.connect() as connection:
        await connection.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        await connection.execute(sa.text(f'CREATE DATABASE "{name}"'))
    scratch = create_async_engine(postgres_url(name))
    try:
        yield scratch
    finally:
        await scratch.dispose()
        async with admin.connect() as connection:
            await connection.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        await admin.dispose()


@pytest.mark.skipif(not POSTGRES, reason="needs TEST_POSTGRES=1")
async def test_every_revision_downgrades_and_upgrades_again_on_postgres() -> None:
    async with _scratch_postgres("downgrade") as scratch:
        async with scratch.begin() as connection:
            await connection.run_sync(upgrade_head)
        async with scratch.begin() as connection:
            await connection.run_sync(_down_and_up)


def _upgrade_with_a_nomination_document(connection) -> int:
    """Upgrade to head with a nomination document on file before aspirant_only runs, and count
    the party files left after."""
    modules = revision_modules()
    at = next(i for i, m in enumerate(modules) if m.revision == "aspirant_only")
    file_id, document_id, aspirant_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with Operations.context(MigrationContext.configure(connection)):
        for module in modules[:at]:
            module.upgrade()
        connection.execute(sa.text("SET session_replication_role = replica"))
        connection.execute(
            sa.text(
                "INSERT INTO stored_files "
                "(id, area, public, original_name, content_type, size, sha256, widths) "
                "VALUES (:id, 'nominations', false, 'form.pdf', 'application/pdf', 1, :sha, '[]')"
            ),
            {"id": file_id, "sha": "0" * 64},
        )
        connection.execute(
            sa.text(
                "INSERT INTO aspirant_documents (id, aspirant_id, label, file_id) "
                "VALUES (:id, :aspirant, 'Nomination form', :file)"
            ),
            {"id": document_id, "aspirant": aspirant_id, "file": file_id},
        )
        connection.execute(sa.text("SET session_replication_role = origin"))
        for module in modules[at:]:
            module.upgrade()
    return connection.scalar(sa.text("SELECT count(*) FROM stored_files"))


@pytest.mark.skipif(not POSTGRES, reason="needs TEST_POSTGRES=1")
async def test_aspirant_only_removes_party_files_a_party_table_still_points_at() -> None:
    async with _scratch_postgres("party_files") as scratch, scratch.begin() as connection:
        left = await connection.run_sync(_upgrade_with_a_nomination_document)

    assert left == 0


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
        assert f"CREATE TABLE {table}" in sql or f"RENAME TO {table}" in sql, table
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
        "CREATE UNIQUE INDEX uq_campaign_members_one_manager ON campaign_members "
        "(campaign_id) WHERE role = 'manager'" in sql
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
