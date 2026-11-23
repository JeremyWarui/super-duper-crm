"""Past election results: elections, contests and each candidate's votes.

Shared reference data for the competitive target, loaded by `campaign-crm seed-results`.

Revision ID: election_results
Revises: president
Create Date: 2026-11-23 14:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "election_results"
down_revision: str | None = "president"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "elections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_elections")),
        sa.UniqueConstraint("name", name=op.f("uq_elections_name")),
    )
    op.create_index(op.f("ix_elections_year"), "elections", ["year"], unique=False)

    op.create_table(
        "contests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("election_id", sa.Uuid(), nullable=False),
        sa.Column(
            "office",
            sa.Enum(
                "president",
                "governor",
                "senator",
                "women_rep",
                "mp",
                "mca",
                name="result_office",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "level",
            sa.Enum(
                "county",
                "constituency",
                "ward",
                name="result_level",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("county_code", sa.String(length=10), nullable=False),
        sa.Column("constituency_code", sa.String(length=10), nullable=False),
        sa.Column("ward_code", sa.String(length=10), nullable=False),
        sa.Column("county_id", sa.Uuid(), nullable=True),
        sa.Column("constituency_id", sa.Uuid(), nullable=True),
        sa.Column("ward_id", sa.Uuid(), nullable=True),
        sa.Column("area_name", sa.String(length=100), nullable=False),
        sa.Column("total_votes", sa.Integer(), nullable=True),
        sa.Column("registered_voters", sa.Integer(), nullable=True),
        sa.Column("unopposed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("excluded", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.String(length=200), nullable=False),
        sa.CheckConstraint(
            "registered_voters IS NULL OR registered_voters >= 0",
            name=op.f("ck_contests_registered_voters_non_negative"),
        ),
        sa.CheckConstraint(
            "total_votes IS NULL OR total_votes >= 0",
            name=op.f("ck_contests_total_votes_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["constituency_id"],
            ["constituencies.id"],
            name=op.f("fk_contests_constituency_id_constituencies"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["county_id"],
            ["counties.id"],
            name=op.f("fk_contests_county_id_counties"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["election_id"],
            ["elections.id"],
            name=op.f("fk_contests_election_id_elections"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ward_id"], ["wards.id"], name=op.f("fk_contests_ward_id_wards"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contests")),
        sa.UniqueConstraint(
            "election_id",
            "office",
            "county_code",
            "constituency_code",
            "ward_code",
            name="uq_contests_area",
        ),
    )
    op.create_index(
        op.f("ix_contests_constituency_id"), "contests", ["constituency_id"], unique=False
    )
    op.create_index(op.f("ix_contests_county_id"), "contests", ["county_id"], unique=False)
    op.create_index(op.f("ix_contests_election_id"), "contests", ["election_id"], unique=False)
    op.create_index(op.f("ix_contests_ward_id"), "contests", ["ward_id"], unique=False)

    op.create_table(
        "contest_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contest_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("party", sa.String(length=100), nullable=False),
        sa.Column("votes", sa.Integer(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("is_winner", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint(
            "votes IS NULL OR votes >= 0", name=op.f("ck_contest_candidates_votes_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["contest_id"],
            ["contests.id"],
            name=op.f("fk_contest_candidates_contest_id_contests"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contest_candidates")),
    )
    op.create_index(
        op.f("ix_contest_candidates_contest_id"),
        "contest_candidates",
        ["contest_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_contest_candidates_contest_id"), table_name="contest_candidates")
    op.drop_table("contest_candidates")
    op.drop_index(op.f("ix_contests_ward_id"), table_name="contests")
    op.drop_index(op.f("ix_contests_election_id"), table_name="contests")
    op.drop_index(op.f("ix_contests_county_id"), table_name="contests")
    op.drop_index(op.f("ix_contests_constituency_id"), table_name="contests")
    op.drop_table("contests")
    op.drop_index(op.f("ix_elections_year"), table_name="elections")
    op.drop_table("elections")
