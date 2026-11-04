"""Remove hosting and finance: plans, subscriptions, party payments and the Finance Officer.

Revision ID: remove_hosting_finance
Revises: site_settings
Create Date: 2026-11-05 11:00:00.000000

Downgrade restores the tables and columns empty, with an unpaid subscription per campaign.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "remove_hosting_finance"
down_revision: str | None = "site_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LIVE_PAYMENT = "kind = 'payment' AND voided_at IS NULL"
OFFICES = ("membership_officer", "nominations_officer")


def _set_offices(*offices: str) -> None:
    """Replace the CHECK listing the party offices a login may hold.

    The old CHECK is looked up, as its name depends on how the table was first migrated.
    """
    allowed = "role IN (" + ", ".join(f"'{office}'" for office in offices) + ")"
    name = op.f("ck_party_roles_party_role")
    if op.get_context().as_sql:
        # Rendered SQL names the CHECK as `alembic upgrade` creates it.
        olds = [name]
    else:
        olds = [
            check["name"]
            for check in sa.inspect(op.get_bind()).get_check_constraints("party_roles")
            if "role" in check["sqltext"] and "kind" not in check["sqltext"]
        ]
    with op.batch_alter_table("party_roles") as batch:
        for old in olds:
            batch.drop_constraint(op.f(old), type_="check")
        batch.create_check_constraint(name, allowed)


def upgrade() -> None:
    op.execute("DELETE FROM party_roles WHERE role = 'finance_officer'")
    _set_offices(*OFFICES)

    op.drop_table("party_payments")
    op.drop_table("subscription_entries")
    op.drop_table("campaign_subscriptions")
    op.drop_table("crm_plans")

    with op.batch_alter_table("party_settings") as batch:
        batch.drop_constraint(op.f("ck_party_settings_grace_days_range"), type_="check")
        batch.drop_constraint(op.f("ck_party_settings_read_only_days_range"), type_="check")
        batch.drop_column("grace_days")
        batch.drop_column("read_only_days")
        batch.drop_column("hosting_enabled")


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, length=20, create_constraint=True)


def _timestamp(name: str) -> sa.Column:
    return sa.Column(
        name, sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False
    )


def _fk(table: str, column: str, target: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column],
        [f"{target}.id"],
        name=op.f(f"fk_{table}_{column}_{target}"),
        ondelete=ondelete,
    )


def downgrade() -> None:
    with op.batch_alter_table("party_settings") as batch:
        batch.add_column(
            sa.Column("grace_days", sa.Integer(), server_default=sa.text("7"), nullable=False)
        )
        batch.add_column(
            sa.Column("read_only_days", sa.Integer(), server_default=sa.text("7"), nullable=False)
        )
        batch.add_column(
            sa.Column("hosting_enabled", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch.create_check_constraint(
            op.f("ck_party_settings_grace_days_range"), "grace_days BETWEEN 0 AND 60"
        )
        batch.create_check_constraint(
            op.f("ck_party_settings_read_only_days_range"), "read_only_days BETWEEN 0 AND 60"
        )

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
        _fk("campaign_subscriptions", "campaign_id", "campaigns", "SET NULL"),
        _fk("campaign_subscriptions", "plan_id", "crm_plans", "RESTRICT"),
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
        _fk("subscription_entries", "subscription_id", "campaign_subscriptions", "RESTRICT"),
        _fk("subscription_entries", "plan_id", "crm_plans", "RESTRICT"),
        _fk("subscription_entries", "recorded_by_id", "users", "SET NULL"),
        _fk("subscription_entries", "voided_by_id", "users", "SET NULL"),
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
    new_id = (
        "gen_random_uuid()"
        if op.get_context().dialect.name == "postgresql"
        else "lower(hex(randomblob(16)))"
    )
    op.execute(
        "INSERT INTO campaign_subscriptions (id, campaign_id, hold) "
        f"SELECT {new_id}, id, 'none' FROM campaigns"
    )

    op.create_table(
        "party_payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "payee_kind",
            _enum("payee_kind", "polling_agent", "party_agent", "volunteer", "member", "staff"),
            nullable=False,
        ),
        sa.Column("member_id", sa.Uuid(), nullable=True),
        sa.Column("volunteer_id", sa.Uuid(), nullable=True),
        sa.Column("registration_centre_id", sa.Uuid(), nullable=True),
        sa.Column("polling_station", sa.String(200), nullable=False, server_default=""),
        sa.Column("aspirant_id", sa.Uuid(), nullable=True),
        sa.Column("campaign_label", sa.String(200), nullable=False, server_default=""),
        sa.Column("purpose", sa.String(150), nullable=False, server_default=""),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("recipient_name", sa.String(150), nullable=False),
        sa.Column("recipient_phone", sa.String(20), nullable=False, server_default=""),
        sa.Column("amount_kes", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            _enum("payment_status", "scheduled", "sending", "paid", "failed", "cancelled"),
            nullable=False,
        ),
        sa.Column("reference", sa.String(50), nullable=False, server_default=""),
        sa.Column("provider", sa.String(20), nullable=False, server_default=""),
        sa.Column("failure_reason", sa.String(200), nullable=False, server_default=""),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sending_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("approved_by_id", sa.Uuid(), nullable=True),
        sa.Column("approved_by_name", sa.String(150), nullable=False, server_default=""),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("amount_kes > 0", name=op.f("ck_party_payments_amount_kes_positive")),
        sa.CheckConstraint(
            "member_id IS NULL OR volunteer_id IS NULL", name=op.f("ck_party_payments_one_register")
        ),
        _fk("party_payments", "member_id", "party_members", "SET NULL"),
        _fk("party_payments", "volunteer_id", "volunteer_profiles", "SET NULL"),
        _fk("party_payments", "registration_centre_id", "registration_centres", "SET NULL"),
        _fk("party_payments", "aspirant_id", "aspirants", "SET NULL"),
        _fk("party_payments", "created_by_id", "users", "SET NULL"),
        _fk("party_payments", "approved_by_id", "users", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_party_payments")),
    )
    op.create_index(op.f("ix_party_payments_member_id"), "party_payments", ["member_id"])
    op.create_index(op.f("ix_party_payments_volunteer_id"), "party_payments", ["volunteer_id"])
    op.create_index(op.f("ix_party_payments_aspirant_id"), "party_payments", ["aspirant_id"])
    op.create_index(op.f("ix_party_payments_reference"), "party_payments", ["reference"])

    _set_offices(*OFFICES, "finance_officer")
