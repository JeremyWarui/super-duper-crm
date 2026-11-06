"""Retired areas, a report of every reference data import, and the register each target
was worked out on.

Revision ID: reference_imports
Revises: setup_tokens
Create Date: 2026-11-07 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "reference_imports"
down_revision: str | None = "setup_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AREAS = ("counties", "constituencies", "wards", "registration_centres")


def upgrade() -> None:
    for table in AREAS:
        with op.batch_alter_table(table) as batch:
            batch.add_column(
                sa.Column("retired", sa.Boolean(), server_default=sa.false(), nullable=False)
            )
    with op.batch_alter_table("targets") as batch:
        batch.add_column(sa.Column("registered_voters", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE targets SET registered_voters = (SELECT registration_centres.registered_voters "
        "FROM registration_centres WHERE registration_centres.id = targets.registration_centre_id) "
        "WHERE registration_centre_id IS NOT NULL"
    )
    op.execute(
        "UPDATE targets SET registered_voters = (SELECT wards.registered_voters FROM wards "
        "WHERE wards.id = targets.ward_id) WHERE registration_centre_id IS NULL"
    )
    op.create_table(
        "import_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("rows", sa.Integer(), nullable=False),
        sa.Column("counts", sa.JSON(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_import_runs_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_runs")),
    )
    op.create_table(
        "import_changes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("level", sa.String(20), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("change", sa.String(20), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["import_runs.id"],
            name=op.f("fk_import_changes_run_id_import_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_changes")),
    )
    op.create_index(op.f("ix_import_changes_run_id"), "import_changes", ["run_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_import_changes_run_id"), table_name="import_changes")
    op.drop_table("import_changes")
    op.drop_table("import_runs")
    with op.batch_alter_table("targets") as batch:
        batch.drop_column("registered_voters")
    for table in reversed(AREAS):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("retired")
