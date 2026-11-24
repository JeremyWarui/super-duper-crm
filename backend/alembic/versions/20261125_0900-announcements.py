"""Announcements to a unit's team, and calls for one registration centre.

Revision ID: announcements
Revises: notices
Create Date: 2026-11-25 09:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "announcements"
down_revision: str | None = "notices"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "announcements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("ward_id", sa.Uuid(), nullable=True),
        sa.Column("registration_centre_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_announcements_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            name=op.f("fk_announcements_author_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ward_id"],
            ["wards.id"],
            name=op.f("fk_announcements_ward_id_wards"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["registration_centre_id"],
            ["registration_centres.id"],
            name=op.f("fk_announcements_registration_centre_id_registration_centres"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_announcements")),
    )
    op.create_index(op.f("ix_announcements_campaign_id"), "announcements", ["campaign_id"])
    with op.batch_alter_table("notices") as batch:
        batch.add_column(sa.Column("announcement_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            op.f("fk_notices_announcement_id_announcements"),
            "announcements",
            ["announcement_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.create_index(op.f("ix_notices_announcement_id"), ["announcement_id"])
    with op.batch_alter_table("meetings") as batch:
        batch.add_column(sa.Column("registration_centre_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            op.f("fk_meetings_registration_centre_id_registration_centres"),
            "registration_centres",
            ["registration_centre_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("meetings") as batch:
        batch.drop_constraint(
            op.f("fk_meetings_registration_centre_id_registration_centres"), type_="foreignkey"
        )
        batch.drop_column("registration_centre_id")
    op.execute("DELETE FROM notices WHERE announcement_id IS NOT NULL")
    with op.batch_alter_table("notices") as batch:
        batch.drop_index(op.f("ix_notices_announcement_id"))
        batch.drop_constraint(op.f("fk_notices_announcement_id_announcements"), type_="foreignkey")
        batch.drop_column("announcement_id")
    op.drop_index(op.f("ix_announcements_campaign_id"), table_name="announcements")
    op.drop_table("announcements")
