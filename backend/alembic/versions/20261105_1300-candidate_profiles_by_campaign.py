"""Candidate profiles keyed by campaign: a surrogate id, campaign_id required, aspirant_id optional.

Revision ID: candidate_profiles_by_campaign
Revises: workspace_kinds
Create Date: 2026-11-05 13:00:00.000000

Each profile takes its aspirant's campaign. A profile whose aspirant has no campaign is deleted.
Downgrade refuses while a profile has no aspirant, as the older schema keys profiles by aspirant.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "candidate_profiles_by_campaign"
down_revision: str | None = "workspace_kinds"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_ID = {"postgresql": "gen_random_uuid()", "sqlite": "lower(hex(randomblob(16)))"}


def upgrade() -> None:
    with op.batch_alter_table("candidate_profiles") as batch:
        batch.add_column(sa.Column("id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("campaign_id", sa.Uuid(), nullable=True))
    op.execute(
        "UPDATE candidate_profiles SET campaign_id = (SELECT aspirants.campaign_id FROM aspirants "
        "WHERE aspirants.id = candidate_profiles.aspirant_id), "
        f"id = {NEW_ID[op.get_context().dialect.name]}"
    )
    op.execute("DELETE FROM candidate_profiles WHERE campaign_id IS NULL")
    with op.batch_alter_table("candidate_profiles") as batch:
        batch.drop_constraint(op.f("pk_candidate_profiles"), type_="primary")
        batch.alter_column("id", existing_type=sa.Uuid(), nullable=False)
        batch.alter_column("campaign_id", existing_type=sa.Uuid(), nullable=False)
        batch.alter_column("aspirant_id", existing_type=sa.Uuid(), nullable=True)
        batch.create_primary_key(op.f("pk_candidate_profiles"), ["id"])
        batch.create_unique_constraint(op.f("uq_candidate_profiles_campaign_id"), ["campaign_id"])
        batch.create_unique_constraint(op.f("uq_candidate_profiles_aspirant_id"), ["aspirant_id"])
        batch.create_foreign_key(
            op.f("fk_candidate_profiles_campaign_id_campaigns"),
            "campaigns",
            ["campaign_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    if not op.get_context().as_sql and op.get_bind().scalar(
        sa.text("SELECT count(*) FROM candidate_profiles WHERE aspirant_id IS NULL")
    ):
        raise RuntimeError("A candidate profile has no aspirant; remove it before downgrading.")
    with op.batch_alter_table("candidate_profiles") as batch:
        batch.drop_constraint(
            op.f("fk_candidate_profiles_campaign_id_campaigns"), type_="foreignkey"
        )
        batch.drop_constraint(op.f("uq_candidate_profiles_aspirant_id"), type_="unique")
        batch.drop_constraint(op.f("uq_candidate_profiles_campaign_id"), type_="unique")
        batch.drop_constraint(op.f("pk_candidate_profiles"), type_="primary")
        batch.alter_column("aspirant_id", existing_type=sa.Uuid(), nullable=False)
        batch.create_primary_key(op.f("pk_candidate_profiles"), ["aspirant_id"])
        batch.drop_column("campaign_id")
        batch.drop_column("id")
