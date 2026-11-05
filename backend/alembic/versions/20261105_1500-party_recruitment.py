"""Party recruitment: who recruited an applicant, from which county, and coordinators' codes.

Revision ID: party_recruitment
Revises: campaign_roles
Create Date: 2026-11-05 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "party_recruitment"
down_revision: str | None = "campaign_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("party_members") as batch:
        batch.add_column(sa.Column("recruited_by_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("recruitment_county_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            op.f("fk_party_members_recruited_by_id_campaign_members"),
            "campaign_members",
            ["recruited_by_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_foreign_key(
            op.f("fk_party_members_recruitment_county_id_counties"),
            "counties",
            ["recruitment_county_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index(op.f("ix_party_members_recruited_by_id"), ["recruited_by_id"])
    op.create_table(
        "recruitment_codes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_member_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["campaign_member_id"],
            ["campaign_members.id"],
            name=op.f("fk_recruitment_codes_campaign_member_id_campaign_members"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recruitment_codes")),
        sa.UniqueConstraint("code", name=op.f("uq_recruitment_codes_code")),
    )
    op.create_index(
        op.f("ix_recruitment_codes_campaign_member_id"),
        "recruitment_codes",
        ["campaign_member_id"],
    )
    op.create_index(
        "uq_recruitment_codes_one_active",
        "recruitment_codes",
        ["campaign_member_id"],
        unique=True,
        sqlite_where=sa.text("active"),
        postgresql_where=sa.text("active"),
    )


def downgrade() -> None:
    op.drop_index("uq_recruitment_codes_one_active", table_name="recruitment_codes")
    op.drop_index(op.f("ix_recruitment_codes_campaign_member_id"), table_name="recruitment_codes")
    op.drop_table("recruitment_codes")
    with op.batch_alter_table("party_members") as batch:
        batch.drop_index(op.f("ix_party_members_recruited_by_id"))
        batch.drop_constraint(
            op.f("fk_party_members_recruitment_county_id_counties"), type_="foreignkey"
        )
        batch.drop_constraint(
            op.f("fk_party_members_recruited_by_id_campaign_members"), type_="foreignkey"
        )
        batch.drop_column("recruitment_county_id")
        batch.drop_column("recruited_by_id")
