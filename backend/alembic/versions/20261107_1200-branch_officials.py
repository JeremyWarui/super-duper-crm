"""Branch officials as terms in office, linked to party members, with minutes as files.

Each branch's chairperson and secretary text becomes a current term. It is linked to the one
approved member with that exact name; otherwise the name is kept with a note saying so.

Revision ID: branch_officials
Revises: backup_runs
Create Date: 2026-11-07 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "branch_officials"
down_revision: str | None = "backup_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OFFICES = (
    "office IN ('chair', 'secretary', 'treasurer', 'organising_secretary', "
    "'youth_leader', 'women_leader', 'other')"
)
STARTS = "start_reason IN ('elected', 'interim', 'recorded')"
ENDS = "end_reason IN ('replaced', 'resigned', 'removed', 'completed')"
AREAS_BEFORE = "area IN ('site', 'slides', 'leaders', 'documents', 'candidates')"
AREAS_AFTER = "area IN ('site', 'slides', 'leaders', 'documents', 'candidates', 'minutes')"
OLD_FIELDS = (("chair", "chairperson"), ("secretary", "secretary"))


def _carry_over(office: str, column: str, postgres: bool) -> str:
    """An INSERT making the text in `column` the branch's current term in `office`."""
    new_id = "gen_random_uuid()" if postgres else "lower(hex(randomblob(16)))"
    day = "CAST(b.updated_at AS DATE)" if postgres else "date(b.updated_at)"
    same = f"lower(trim(m.full_name)) = lower(trim(b.{column})) AND m.status = 'approved'"
    matches = f"(SELECT count(*) FROM party_members m WHERE {same})"
    note = f"Carried over from the old {column} field; no single approved member has this name."
    return (
        "INSERT INTO branch_officials (id, branch_id, member_id, office, title, holder_name, "
        "term_start, start_reason, note) "
        f"SELECT {new_id}, b.id, "
        f"CASE WHEN {matches} = 1 THEN (SELECT m.id FROM party_members m WHERE {same}) END, "
        f"'{office}', '', trim(b.{column}), {day}, 'recorded', "
        f"CASE WHEN {matches} = 1 THEN '' ELSE '{note}' END "
        f"FROM branches b WHERE trim(b.{column}) <> ''"
    )


def upgrade() -> None:
    postgres = op.get_context().dialect.name == "postgresql"
    op.create_table(
        "branch_officials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=True),
        sa.Column("office", sa.String(30), nullable=False),
        sa.Column("title", sa.String(80), server_default="", nullable=False),
        sa.Column("holder_name", sa.String(150), nullable=False),
        sa.Column("term_start", sa.Date(), nullable=False),
        sa.Column("term_end", sa.Date(), nullable=True),
        sa.Column("start_reason", sa.String(20), nullable=False),
        sa.Column("end_reason", sa.String(20), nullable=True),
        sa.Column("minutes_file_id", sa.Uuid(), nullable=True),
        sa.Column("note", sa.Text(), server_default="", nullable=False),
        sa.Column("appointed_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "term_end IS NULL OR term_end >= term_start",
            name=op.f("ck_branch_officials_term_in_order"),
        ),
        sa.CheckConstraint(OFFICES, name=op.f("ck_branch_officials_branch_office")),
        sa.CheckConstraint(STARTS, name=op.f("ck_branch_officials_term_start_reason")),
        sa.CheckConstraint(ENDS, name=op.f("ck_branch_officials_term_end_reason")),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["branches.id"],
            name=op.f("fk_branch_officials_branch_id_branches"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["party_members.id"],
            name=op.f("fk_branch_officials_member_id_party_members"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["minutes_file_id"],
            ["stored_files.id"],
            name=op.f("fk_branch_officials_minutes_file_id_stored_files"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["appointed_by_id"],
            ["users.id"],
            name=op.f("fk_branch_officials_appointed_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_branch_officials")),
    )
    op.create_index(op.f("ix_branch_officials_branch_id"), "branch_officials", ["branch_id"])
    op.create_index(op.f("ix_branch_officials_member_id"), "branch_officials", ["member_id"])
    op.create_index(
        "uq_branch_officials_open_term",
        "branch_officials",
        ["branch_id", "office"],
        unique=True,
        postgresql_where=sa.text("term_end IS NULL AND office <> 'other'"),
        sqlite_where=sa.text("term_end IS NULL AND office <> 'other'"),
    )
    for office, column in OLD_FIELDS:
        op.execute(_carry_over(office, column, postgres))
    with op.batch_alter_table("branches") as batch:
        batch.drop_column("chairperson")
        batch.drop_column("secretary")
    with op.batch_alter_table("stored_files") as batch:
        batch.drop_constraint(op.f("ck_stored_files_file_area"), type_="check")
        batch.create_check_constraint(op.f("ck_stored_files_file_area"), AREAS_AFTER)


def downgrade() -> None:
    op.execute("DELETE FROM stored_files WHERE area = 'minutes'")
    with op.batch_alter_table("stored_files") as batch:
        batch.drop_constraint(op.f("ck_stored_files_file_area"), type_="check")
        batch.create_check_constraint(op.f("ck_stored_files_file_area"), AREAS_BEFORE)
    with op.batch_alter_table("branches") as batch:
        batch.add_column(
            sa.Column("chairperson", sa.String(150), server_default="", nullable=False)
        )
        batch.add_column(sa.Column("secretary", sa.String(150), server_default="", nullable=False))
    for office, column in OLD_FIELDS:
        op.execute(
            f"UPDATE branches SET {column} = COALESCE((SELECT o.holder_name FROM branch_officials o "
            f"WHERE o.branch_id = branches.id AND o.office = '{office}' AND o.term_end IS NULL "
            "ORDER BY o.term_start DESC LIMIT 1), '')"
        )
    op.drop_index("uq_branch_officials_open_term", table_name="branch_officials")
    op.drop_index(op.f("ix_branch_officials_member_id"), table_name="branch_officials")
    op.drop_index(op.f("ix_branch_officials_branch_id"), table_name="branch_officials")
    op.drop_table("branch_officials")
