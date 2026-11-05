"""Uploaded files, and a file column beside each image or document URL.

Revision ID: stored_files
Revises: party_recruitment
Create Date: 2026-11-05 16:00:00.000000

The `*_url` columns stay as fallbacks.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "stored_files"
down_revision: str | None = "party_recruitment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AREAS = "area IN ('site', 'slides', 'leaders', 'documents', 'candidates')"
# Each table and the file column it gains.
COLUMNS = (
    ("site_settings", "logo_file_id"),
    ("hero_slides", "image_file_id"),
    ("party_leaders", "photo_file_id"),
    ("party_documents", "file_id"),
    ("candidate_profiles", "photo_file_id"),
)


def upgrade() -> None:
    op.create_table(
        "stored_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("area", sa.String(20), nullable=False),
        sa.Column("public", sa.Boolean(), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("widths", sa.JSON(), nullable=False),
        sa.Column("uploaded_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(AREAS, name=op.f("ck_stored_files_file_area")),
        sa.ForeignKeyConstraint(
            ["uploaded_by_id"],
            ["users.id"],
            name=op.f("fk_stored_files_uploaded_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stored_files")),
    )
    op.create_index(op.f("ix_stored_files_sha256"), "stored_files", ["sha256"])
    for table, column in COLUMNS:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column(column, sa.Uuid(), nullable=True))
            batch.create_foreign_key(
                op.f(f"fk_{table}_{column}_stored_files"),
                "stored_files",
                [column],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    for table, column in COLUMNS:
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(op.f(f"fk_{table}_{column}_stored_files"), type_="foreignkey")
            batch.drop_column(column)
    op.drop_index(op.f("ix_stored_files_sha256"), table_name="stored_files")
    op.drop_table("stored_files")
