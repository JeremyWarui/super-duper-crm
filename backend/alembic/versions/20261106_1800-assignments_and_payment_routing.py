"""Assignments, and payments made against them with approval routing.

Revision ID: assignments_and_payment_routing
Revises: team_registrations_and_agents
Create Date: 2026-11-06 18:00:00.000000

Payments made before this keep no assignment and stay approved by the manager.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "assignments_and_payment_routing"
down_revision: str | None = "team_registrations_and_agents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLES = "approver_role IN ('candidate', 'manager', 'coordinator', 'comms', 'mobilizer', 'agent')"
LIVE = "status <> 'cancelled'"
PAYMENT_FKS = (
    ("assignment_id", "assignments", "SET NULL"),
    ("agent_id", "agents", "SET NULL"),
    ("scheduled_by_id", "users", "SET NULL"),
    ("approved_by_id", "users", "SET NULL"),
)


def upgrade() -> None:
    op.create_table(
        "assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("mobilizer_id", sa.Uuid(), nullable=True),
        sa.Column("agent_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=True),
        sa.Column("ward_id", sa.Uuid(), nullable=True),
        sa.Column("registration_centre_id", sa.Uuid(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("amount_kes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("done_by_id", sa.Uuid(), nullable=True),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "(mobilizer_id IS NULL) <> (agent_id IS NULL)", name=op.f("ck_assignments_one_member")
        ),
        sa.CheckConstraint("amount_kes > 0", name=op.f("ck_assignments_amount_kes_positive")),
        sa.CheckConstraint(
            "kind IN ('event', 'ward_work', 'activity')",
            name=op.f("ck_assignments_assignment_kind"),
        ),
        sa.CheckConstraint(
            "status IN ('assigned', 'done', 'cancelled')",
            name=op.f("ck_assignments_assignment_status"),
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_assignments_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["mobilizer_id"],
            ["mobilizers.id"],
            name=op.f("fk_assignments_mobilizer_id_mobilizers"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            name=op.f("fk_assignments_agent_id_agents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name=op.f("fk_assignments_event_id_events"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ward_id"],
            ["wards.id"],
            name=op.f("fk_assignments_ward_id_wards"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["registration_centre_id"],
            ["registration_centres.id"],
            name=op.f("fk_assignments_registration_centre_id_registration_centres"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_assignments_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["done_by_id"],
            ["users.id"],
            name=op.f("fk_assignments_done_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assignments")),
    )
    for column in ("campaign_id", "mobilizer_id", "agent_id", "event_id", "ward_id"):
        op.create_index(op.f(f"ix_assignments_{column}"), "assignments", [column])

    with op.batch_alter_table("payments") as batch:
        for column, _, _ in PAYMENT_FKS:
            batch.add_column(sa.Column(column, sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("approver_role", sa.String(20), nullable=True))
        batch.create_check_constraint(op.f("ck_payments_approver_role"), ROLES)
        for column, table, ondelete in PAYMENT_FKS:
            batch.create_foreign_key(
                op.f(f"fk_payments_{column}_{table}"), table, [column], ["id"], ondelete=ondelete
            )
    op.create_index(op.f("ix_payments_assignment_id"), "payments", ["assignment_id"])
    op.create_index(op.f("ix_payments_agent_id"), "payments", ["agent_id"])
    op.create_index(
        "uq_payments_assignment",
        "payments",
        ["assignment_id"],
        unique=True,
        postgresql_where=sa.text(LIVE),
        sqlite_where=sa.text(LIVE),
    )


def downgrade() -> None:
    op.drop_index("uq_payments_assignment", table_name="payments")
    op.drop_index(op.f("ix_payments_agent_id"), table_name="payments")
    op.drop_index(op.f("ix_payments_assignment_id"), table_name="payments")
    with op.batch_alter_table("payments") as batch:
        for column, table, _ in PAYMENT_FKS:
            batch.drop_constraint(op.f(f"fk_payments_{column}_{table}"), type_="foreignkey")
        batch.drop_constraint(op.f("ck_payments_approver_role"), type_="check")
        batch.drop_column("approver_role")
        for column, _, _ in PAYMENT_FKS:
            batch.drop_column(column)
    for column in ("campaign_id", "mobilizer_id", "agent_id", "event_id", "ward_id"):
        op.drop_index(op.f(f"ix_assignments_{column}"), table_name="assignments")
    op.drop_table("assignments")
