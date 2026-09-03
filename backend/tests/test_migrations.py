"""The migrations build the same schema the models describe.

Catches a column added to a model but never migrated. Names are compared, not
column types, which differ harmlessly across databases.
"""

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from backend.models import Base

VERSIONS_DIR = Path(__file__).resolve().parent.parent / "alembic" / "versions"


def _revision_files() -> list[Path]:
    return sorted(p for p in VERSIONS_DIR.glob("*.py") if not p.name.startswith("_"))


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def migrated_metadata() -> sa.MetaData:
    """Every migration applied in order, then read back."""
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            for path in _revision_files():
                _load(path).upgrade()
        reflected = sa.MetaData()
        reflected.reflect(bind=connection)
    engine.dispose()
    return reflected


def test_there_is_at_least_one_revision() -> None:
    assert _revision_files(), "no Alembic revision found; run alembic revision --autogenerate"


def test_revisions_form_a_single_chain() -> None:
    revisions = [_load(path) for path in _revision_files()]
    roots = [m for m in revisions if m.down_revision is None]
    assert len(roots) == 1, "exactly one revision may have down_revision = None"

    known = {m.revision for m in revisions}
    parents = [m.down_revision for m in revisions if m.down_revision is not None]
    assert set(parents) <= known, "a revision points at a parent that does not exist"
    assert len(parents) == len(set(parents)), "two revisions share a parent (branched history)"


def test_migration_creates_every_table(migrated_metadata: sa.MetaData) -> None:
    assert set(migrated_metadata.tables) == set(Base.metadata.tables)


def test_migration_creates_every_column(migrated_metadata: sa.MetaData) -> None:
    for name, model_table in Base.metadata.tables.items():
        migrated_columns = {c.name for c in migrated_metadata.tables[name].columns}
        model_columns = {c.name for c in model_table.columns}
        assert migrated_columns == model_columns, f"{name} has drifted"


def test_migration_preserves_nullability(migrated_metadata: sa.MetaData) -> None:
    """A required column that the migration made optional fails only later, on
    the first insert that leaves it out."""
    for name, model_table in Base.metadata.tables.items():
        migrated = {c.name: c.nullable for c in migrated_metadata.tables[name].columns}
        for column in model_table.columns:
            assert migrated[column.name] == column.nullable, f"{name}.{column.name}"


def test_migration_creates_every_index(migrated_metadata: sa.MetaData) -> None:
    for name, model_table in Base.metadata.tables.items():
        migrated_indexes = {i.name for i in migrated_metadata.tables[name].indexes}
        model_indexes = {i.name for i in model_table.indexes}
        assert model_indexes <= migrated_indexes, f"{name} is missing an index"


def test_migration_creates_the_partial_unique_indexes(
    migrated_metadata: sa.MetaData,
) -> None:
    """Losing the WHERE clause on these still builds, but stops a campaign from
    holding a ward target and its centre targets at the same time."""
    names = {i.name for i in migrated_metadata.tables["targets"].indexes}
    assert "uq_targets_campaign_ward" in names
    assert "uq_targets_campaign_registration_centre" in names


def test_downgrade_removes_everything_upgrade_created() -> None:
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            revisions = [_load(path) for path in _revision_files()]
            for module in revisions:
                module.upgrade()
            for module in reversed(revisions):
                module.downgrade()
        left_over = sa.MetaData()
        left_over.reflect(bind=connection)
    engine.dispose()
    assert set(left_over.tables) == set()
