"""Subscriptions: CRM plans, a subscription per campaign, its ledger, and the lapse settings.

Revision ID: subscriptions
Revises: aspirants
Create Date: 2026-11-01 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "subscriptions"
down_revision: str | None = "aspirants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LIVE_PAYMENT = "kind = 'payment' AND voided_at IS NULL"


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, length=20, create_constraint=True)


def _timestamp(name: str) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.text("(CURRENT_TIMESTAMP)"),
        nullable=False,
    )


def _user_fk(table: str, column: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["users.id"], name=op.f(f"fk_{table}_{column}_users"), ondelete="SET NULL"
    )


def _subscribe_existing_campaigns() -> None:
    """Give every campaign already in the database an unpaid subscription."""
    # SQLite keeps a UUID as 32 hex characters.
    new_id = (
        "gen_random_uuid()"
        if op.get_context().dialect.name == "postgresql"
        else "lower(hex(randomblob(16)))"
    )
    op.execute(
        "INSERT INTO campaign_subscriptions (id, campaign_id, hold) "
        f"SELECT {new_id}, id, 'none' FROM campaigns"
    )


def upgrade() -> None:
    op.create_table(
        "crm_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("price_kes", sa.Integer(), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.CheckConstraint("price_kes >= 0", name=op.f("ck_crm_plans_price_not_negative")),
        sa.CheckConstraint(
            "duration_days BETWEEN 1 AND 730", name=op.f("ck_crm_plans_duration_range")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crm_plans")),
        sa.UniqueConstraint("name", name=op.f("uq_crm_plans_name")),
    )
    op.create_table(
        "campaign_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("campaign_title", sa.String(150), nullable=True),
        sa.Column("plan_id", sa.Uuid(), nullable=True),
        sa.Column("paid_until", sa.Date(), nullable=True),
        sa.Column(
            "hold", _enum("subscription_hold", "none", "suspended", "cancelled"), nullable=False
        ),
        sa.Column("hold_reason", sa.Text(), nullable=True),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.CheckConstraint(
            "(hold = 'none') = (hold_reason IS NULL)",
            name=op.f("ck_campaign_subscriptions_hold_has_reason"),
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_campaign_subscriptions_campaign_id_campaigns"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["crm_plans.id"],
            name=op.f("fk_campaign_subscriptions_plan_id_crm_plans"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaign_subscriptions")),
        sa.UniqueConstraint("campaign_id", name=op.f("uq_campaign_subscriptions_campaign_id")),
    )
    op.create_table(
        "subscription_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("kind", _enum("entry_kind", "payment", "extension"), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=True),
        sa.Column("amount_kes", sa.Integer(), nullable=True),
        sa.Column(
            "method", _enum("receipt_method", "mpesa", "bank", "cash", "other"), nullable=True
        ),
        sa.Column("reference", sa.String(40), nullable=True),
        sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("paid_until_before", sa.Date(), nullable=True),
        sa.Column("paid_until_after", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("recorded_by_id", sa.Uuid(), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_by_id", sa.Uuid(), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
        _timestamp("created_at"),
        sa.CheckConstraint(
            "(kind = 'payment' AND amount_kes > 0 AND method IS NOT NULL "
            "AND reference IS NOT NULL AND plan_id IS NOT NULL) "
            "OR (kind = 'extension' AND amount_kes IS NULL AND method IS NULL "
            "AND reference IS NULL)",
            name=op.f("ck_subscription_entries_entry_shape"),
        ),
        sa.CheckConstraint(
            "days BETWEEN 1 AND 730", name=op.f("ck_subscription_entries_days_range")
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["campaign_subscriptions.id"],
            name=op.f("fk_subscription_entries_subscription_id_campaign_subscriptions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["crm_plans.id"],
            name=op.f("fk_subscription_entries_plan_id_crm_plans"),
            ondelete="RESTRICT",
        ),
        _user_fk("subscription_entries", "recorded_by_id"),
        _user_fk("subscription_entries", "voided_by_id"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscription_entries")),
    )
    op.create_index(
        "uq_subscription_entries_reference",
        "subscription_entries",
        ["reference"],
        unique=True,
        sqlite_where=sa.text(LIVE_PAYMENT),
        postgresql_where=sa.text(LIVE_PAYMENT),
    )
    op.create_index(
        "ix_subscription_entries_subscription_id_created_at",
        "subscription_entries",
        ["subscription_id", "created_at"],
    )
    with op.batch_alter_table("party_settings") as batch_op:
        batch_op.add_column(
            sa.Column("grace_days", sa.Integer(), server_default=sa.text("7"), nullable=False)
        )
        batch_op.add_column(
            sa.Column("read_only_days", sa.Integer(), server_default=sa.text("7"), nullable=False)
        )
        batch_op.add_column(
            sa.Column(
                "payment_instructions", sa.Text(), server_default=sa.text("''"), nullable=False
            )
        )
        batch_op.create_check_constraint(
            op.f("ck_party_settings_grace_days_range"), "grace_days BETWEEN 0 AND 60"
        )
        batch_op.create_check_constraint(
            op.f("ck_party_settings_read_only_days_range"), "read_only_days BETWEEN 0 AND 60"
        )
    _subscribe_existing_campaigns()


def downgrade() -> None:
    with op.batch_alter_table("party_settings") as batch_op:
        batch_op.drop_constraint("ck_party_settings_read_only_days_range", type_="check")
        batch_op.drop_constraint("ck_party_settings_grace_days_range", type_="check")
        batch_op.drop_column("payment_instructions")
        batch_op.drop_column("read_only_days")
        batch_op.drop_column("grace_days")
    op.drop_table("subscription_entries")
    op.drop_table("campaign_subscriptions")
    op.drop_table("crm_plans")
