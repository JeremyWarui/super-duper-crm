"""Candidate profiles on the website, and the aspirants a party event names.

Revision ID: candidate_profiles
Revises: party_videos
Create Date: 2026-11-04 20:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "candidate_profiles"
down_revision: str | None = "party_videos"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidate_profiles",
        sa.Column("aspirant_id", sa.Uuid(), nullable=False),
        sa.Column("photo_url", sa.String(500), nullable=False, server_default=""),
        sa.Column("slogan", sa.String(120), nullable=False, server_default=""),
        sa.Column("bio", sa.Text(), nullable=False, server_default=""),
        sa.Column("priorities", sa.JSON(), nullable=False),
        sa.Column("office_address", sa.String(300), nullable=False, server_default=""),
        sa.Column("office_phone", sa.String(20), nullable=False, server_default=""),
        sa.Column("office_email", sa.String(254), nullable=False, server_default=""),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["aspirant_id"],
            ["aspirants.id"],
            name=op.f("fk_candidate_profiles_aspirant_id_aspirants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("aspirant_id", name=op.f("pk_candidate_profiles")),
    )
    op.create_table(
        "party_post_aspirants",
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("aspirant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["party_posts.id"],
            name=op.f("fk_party_post_aspirants_post_id_party_posts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["aspirant_id"],
            ["aspirants.id"],
            name=op.f("fk_party_post_aspirants_aspirant_id_aspirants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("post_id", "aspirant_id", name=op.f("pk_party_post_aspirants")),
    )


def downgrade() -> None:
    op.drop_table("party_post_aspirants")
    op.drop_table("candidate_profiles")
