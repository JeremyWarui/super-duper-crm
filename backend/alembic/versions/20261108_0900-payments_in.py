"""Money paid in by M-Pesa, and where the site's M-Pesa payments go.

Revision ID: payments_in
Revises: party_message_constituency
Create Date: 2026-11-08 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "payments_in"
down_revision: str | None = "party_message_constituency"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MPESA = (("mpesa_paybill", 10), ("mpesa_account", 20), ("mpesa_till", 10))


def upgrade() -> None:
    with op.batch_alter_table("site_settings") as batch:
        for name, length in MPESA:
            batch.add_column(
                sa.Column(name, sa.String(length), server_default=sa.text("''"), nullable=False)
            )
    op.create_table(
        "payments_in",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("aspirant_id", sa.Uuid(), nullable=True),
        sa.Column("amount_kes", sa.Integer(), nullable=False),
        sa.Column("payer_name", sa.String(150), nullable=False),
        sa.Column("payer_phone", sa.String(20), nullable=False),
        sa.Column("payer_email", sa.String(254), nullable=False),
        sa.Column("reference", sa.String(64), nullable=False),
        sa.Column("mpesa_code", sa.String(20), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(300), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_id", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "purpose IN ('nomination_fee', 'contribution')",
            name=op.f("ck_payments_in_pay_in_purpose"),
        ),
        sa.CheckConstraint("method IN ('stk', 'manual')", name=op.f("ck_payments_in_pay_in_method")),
        sa.CheckConstraint(
            "status IN ('pending', 'paid', 'to_confirm', 'failed', 'rejected')",
            name=op.f("ck_payments_in_pay_in_status"),
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_payments_in_campaign_id_campaigns"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["aspirant_id"],
            ["aspirants.id"],
            name=op.f("fk_payments_in_aspirant_id_aspirants"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_id"],
            ["users.id"],
            name=op.f("fk_payments_in_decided_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments_in")),
        sa.UniqueConstraint("reference", name=op.f("uq_payments_in_reference")),
    )
    for column in ("status", "campaign_id", "aspirant_id"):
        op.create_index(op.f(f"ix_payments_in_{column}"), "payments_in", [column])


def downgrade() -> None:
    for column in ("status", "campaign_id", "aspirant_id"):
        op.drop_index(op.f(f"ix_payments_in_{column}"), table_name="payments_in")
    op.drop_table("payments_in")
    with op.batch_alter_table("site_settings") as batch:
        for name, _ in reversed(MPESA):
            batch.drop_column(name)
