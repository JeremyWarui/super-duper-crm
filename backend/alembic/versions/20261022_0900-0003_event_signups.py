"""Public sign-up links per event, and one supporter per phone per campaign.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-22 09:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HAS_PHONE = "phone <> ''"


def upgrade() -> None:
    with op.batch_alter_table("events") as batch:
        batch.add_column(sa.Column("signup_code", sa.String(length=24), nullable=True))
        batch.add_column(
            sa.Column("signups_open", sa.Boolean(), nullable=False, server_default=sa.true())
        )
    # One statement, so the migration also renders offline as SQL.
    if op.get_context().dialect.name == "sqlite":
        op.execute("UPDATE events SET signup_code = lower(hex(randomblob(9)))")
    else:
        op.execute("UPDATE events SET signup_code = substr(md5(random()::text || id::text), 1, 18)")
    with op.batch_alter_table("events") as batch:
        batch.alter_column("signup_code", existing_type=sa.String(length=24), nullable=False)
        batch.alter_column("signups_open", existing_type=sa.Boolean(), server_default=None)
        batch.create_unique_constraint(op.f("uq_events_signup_code"), ["signup_code"])

    with op.batch_alter_table("supporters") as batch:
        batch.add_column(sa.Column("event_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            op.f("fk_supporters_event_id_events"),
            "events",
            ["event_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(op.f("ix_supporters_event_id"), "supporters", ["event_id"], unique=False)
    op.create_index(
        "uq_supporters_campaign_phone",
        "supporters",
        ["campaign_id", "phone"],
        unique=True,
        postgresql_where=sa.text(HAS_PHONE),
        sqlite_where=sa.text(HAS_PHONE),
    )


def downgrade() -> None:
    op.drop_index("uq_supporters_campaign_phone", table_name="supporters")
    op.drop_index(op.f("ix_supporters_event_id"), table_name="supporters")
    with op.batch_alter_table("supporters") as batch:
        batch.drop_constraint(op.f("fk_supporters_event_id_events"), type_="foreignkey")
        batch.drop_column("event_id")
    with op.batch_alter_table("events") as batch:
        batch.drop_constraint(op.f("uq_events_signup_code"), type_="unique")
        batch.drop_column("signups_open")
        batch.drop_column("signup_code")
