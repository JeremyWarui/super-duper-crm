"""Reconciliation of the payments ledger with the payout provider.

Revision ID: reconcile_runs
Revises: sms_log
Create Date: 2026-11-07 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "reconcile_runs"
down_revision: str | None = "sms_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reconcile_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("checked", sa.Integer(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reconcile_runs")),
    )
    op.create_table(
        "reconcile_differences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=True),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("reference", sa.String(100), nullable=False),
        sa.Column("ledger", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["reconcile_runs.id"],
            name=op.f("fk_reconcile_differences_run_id_reconcile_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name=op.f("fk_reconcile_differences_payment_id_payments"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_reconcile_differences_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reconcile_differences")),
    )
    for column in ("run_id", "payment_id", "campaign_id"):
        op.create_index(
            op.f(f"ix_reconcile_differences_{column}"), "reconcile_differences", [column]
        )


def downgrade() -> None:
    op.drop_table("reconcile_differences")
    op.drop_table("reconcile_runs")
