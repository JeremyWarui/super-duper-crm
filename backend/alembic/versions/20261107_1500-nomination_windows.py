"""Nomination windows, the seats and fees in each, and members' own applications.

Revision ID: nomination_windows
Revises: reconcile_runs
Create Date: 2026-11-07 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "nomination_windows"
down_revision: str | None = "reconcile_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AREAS_BEFORE = "area IN ('site', 'slides', 'leaders', 'documents', 'candidates', 'minutes')"
AREAS_AFTER = (
    "area IN ('site', 'slides', 'leaders', 'documents', 'candidates', 'minutes', 'nominations')"
)
SEATS = "seat IN ('mca', 'mp', 'governor', 'senator', 'women_rep')"


def _created() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "nomination_windows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("opens_on", sa.Date(), nullable=False),
        sa.Column("closes_on", sa.Date(), nullable=False),
        sa.Column("requirements", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("drafted_by_id", sa.Uuid(), nullable=True),
        sa.Column("published_by_id", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        _created(),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["drafted_by_id"],
            ["users.id"],
            name=op.f("fk_nomination_windows_drafted_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["published_by_id"],
            ["users.id"],
            name=op.f("fk_nomination_windows_published_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_nomination_windows")),
    )
    op.create_index(op.f("ix_nomination_windows_status"), "nomination_windows", ["status"])
    op.create_table(
        "nomination_seats",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("window_id", sa.Uuid(), nullable=False),
        sa.Column("seat", sa.String(20), nullable=False),
        sa.Column("fee_kes", sa.Integer(), nullable=False),
        sa.CheckConstraint(SEATS, name=op.f("ck_nomination_seats_seat")),
        sa.ForeignKeyConstraint(
            ["window_id"],
            ["nomination_windows.id"],
            name=op.f("fk_nomination_seats_window_id_nomination_windows"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_nomination_seats")),
        sa.UniqueConstraint("window_id", "seat", name="uq_nomination_seats_window_seat"),
    )
    op.create_index(op.f("ix_nomination_seats_window_id"), "nomination_seats", ["window_id"])
    op.create_table(
        "aspirant_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("aspirant_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        _created(),
        sa.ForeignKeyConstraint(
            ["aspirant_id"],
            ["aspirants.id"],
            name=op.f("fk_aspirant_documents_aspirant_id_aspirants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["stored_files.id"],
            name=op.f("fk_aspirant_documents_file_id_stored_files"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_aspirant_documents")),
    )
    op.create_index(
        op.f("ix_aspirant_documents_aspirant_id"), "aspirant_documents", ["aspirant_id"]
    )
    with op.batch_alter_table("aspirants") as batch:
        batch.add_column(sa.Column("window_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("fee_kes", sa.Integer(), server_default="0", nullable=False))
        batch.add_column(sa.Column("fee_paid_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(
            sa.Column("fee_reference", sa.String(50), server_default="", nullable=False)
        )
        batch.add_column(sa.Column("fee_marked_by_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("declared_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key(
            op.f("fk_aspirants_window_id_nomination_windows"),
            "nomination_windows",
            ["window_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_foreign_key(
            op.f("fk_aspirants_fee_marked_by_id_users"),
            "users",
            ["fee_marked_by_id"],
            ["id"],
            ondelete="SET NULL",
        )
    with op.batch_alter_table("stored_files") as batch:
        batch.drop_constraint(op.f("ck_stored_files_file_area"), type_="check")
        batch.create_check_constraint(op.f("ck_stored_files_file_area"), AREAS_AFTER)


def downgrade() -> None:
    op.drop_table("aspirant_documents")
    op.execute("DELETE FROM stored_files WHERE area = 'nominations'")
    with op.batch_alter_table("stored_files") as batch:
        batch.drop_constraint(op.f("ck_stored_files_file_area"), type_="check")
        batch.create_check_constraint(op.f("ck_stored_files_file_area"), AREAS_BEFORE)
    with op.batch_alter_table("aspirants") as batch:
        batch.drop_constraint(op.f("fk_aspirants_fee_marked_by_id_users"), type_="foreignkey")
        batch.drop_constraint(op.f("fk_aspirants_window_id_nomination_windows"), type_="foreignkey")
        for column in (
            "declared_at",
            "fee_marked_by_id",
            "fee_reference",
            "fee_paid_at",
            "fee_kes",
            "window_id",
        ):
            batch.drop_column(column)
    op.drop_table("nomination_seats")
    op.drop_table("nomination_windows")
