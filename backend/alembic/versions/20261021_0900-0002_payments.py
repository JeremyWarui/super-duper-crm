"""Payments to mobilizers, per event.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-21 09:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LIVE = "status <> 'cancelled'"


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=True),
        sa.Column("mobilizer_id", sa.Uuid(), nullable=True),
        sa.Column("recipient_name", sa.String(length=150), nullable=False),
        sa.Column("recipient_phone", sa.String(length=20), nullable=False),
        sa.Column("event_title", sa.String(length=150), nullable=False),
        sa.Column("amount_kes", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "scheduled",
                "sending",
                "paid",
                "failed",
                "cancelled",
                name="payment_status",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("reference", sa.String(length=50), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("failure_reason", sa.String(length=200), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("sending_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint("amount_kes > 0", name=op.f("ck_payments_amount_kes_positive")),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_payments_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"], ["events.id"], name=op.f("fk_payments_event_id_events"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["mobilizer_id"],
            ["mobilizers.id"],
            name=op.f("fk_payments_mobilizer_id_mobilizers"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments")),
    )
    op.create_index(op.f("ix_payments_campaign_id"), "payments", ["campaign_id"], unique=False)
    op.create_index(op.f("ix_payments_event_id"), "payments", ["event_id"], unique=False)
    op.create_index(op.f("ix_payments_mobilizer_id"), "payments", ["mobilizer_id"], unique=False)
    op.create_index(op.f("ix_payments_reference"), "payments", ["reference"], unique=False)
    op.create_index(
        "uq_payments_event_mobilizer",
        "payments",
        ["event_id", "mobilizer_id"],
        unique=True,
        postgresql_where=sa.text(LIVE),
        sqlite_where=sa.text(LIVE),
    )


def downgrade() -> None:
    op.drop_index("uq_payments_event_mobilizer", table_name="payments")
    op.drop_index(op.f("ix_payments_reference"), table_name="payments")
    op.drop_index(op.f("ix_payments_mobilizer_id"), table_name="payments")
    op.drop_index(op.f("ix_payments_event_id"), table_name="payments")
    op.drop_index(op.f("ix_payments_campaign_id"), table_name="payments")
    op.drop_table("payments")
