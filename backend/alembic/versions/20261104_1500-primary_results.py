"""Primary results for the Results page, and the Vie with us page's steps.

Revision ID: primary_results
Revises: about_content
Create Date: 2026-11-04 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "primary_results"
down_revision: str | None = "about_content"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEATS = ("mca", "mp", "governor", "senator", "women_rep")


def upgrade() -> None:
    with op.batch_alter_table("party_settings") as batch:
        batch.add_column(sa.Column("aspirant_steps", sa.Text(), nullable=False, server_default=""))
    op.create_table(
        "primary_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "seat",
            sa.Enum(*SEATS, name="seat", native_enum=False, create_constraint=True, length=20),
            nullable=False,
        ),
        sa.Column("area", sa.String(150), nullable=False),
        sa.Column("candidate", sa.String(150), nullable=False),
        sa.Column("votes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("declared_on", sa.Date(), nullable=True),
        sa.Column("demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("votes >= 0", name=op.f("ck_primary_results_votes_not_negative")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_primary_results")),
    )


def downgrade() -> None:
    op.drop_table("primary_results")
    with op.batch_alter_table("party_settings") as batch:
        batch.drop_column("aspirant_steps")
