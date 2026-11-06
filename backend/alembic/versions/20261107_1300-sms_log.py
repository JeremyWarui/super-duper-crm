"""Texts: the delivery log, opt-outs, inbound replies and workspace messages.

Revision ID: sms_log
Revises: branch_officials
Create Date: 2026-11-07 13:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "sms_log"
down_revision: str | None = "branch_officials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _created() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "campaign_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("wards", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("drafted_by_id", sa.Uuid(), nullable=True),
        sa.Column("decided_by_id", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("recipients", sa.Integer(), nullable=False),
        _created(),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_campaign_messages_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["drafted_by_id"],
            ["users.id"],
            name=op.f("fk_campaign_messages_drafted_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_id"],
            ["users.id"],
            name=op.f("fk_campaign_messages_decided_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaign_messages")),
    )
    op.create_index(
        op.f("ix_campaign_messages_campaign_id"), "campaign_messages", ["campaign_id"]
    )

    op.create_table(
        "sms_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column("event_id", sa.Uuid(), nullable=True),
        sa.Column("sender_id", sa.Uuid(), nullable=True),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_id", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        _created(),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_sms_log_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["campaign_messages.id"],
            name=op.f("fk_sms_log_message_id_campaign_messages"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name=op.f("fk_sms_log_event_id_events"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["sender_id"],
            ["users.id"],
            name=op.f("fk_sms_log_sender_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sms_log")),
        sa.UniqueConstraint("provider_id", name=op.f("uq_sms_log_provider_id")),
    )
    for column in ("campaign_id", "message_id", "event_id", "phone"):
        op.create_index(op.f(f"ix_sms_log_{column}"), "sms_log", [column])

    op.create_table(
        "sms_opt_outs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("source", sa.String(20), nullable=False),
        _created(),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_sms_opt_outs_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sms_opt_outs")),
    )
    op.create_index(op.f("ix_sms_opt_outs_phone"), "sms_opt_outs", ["phone"])
    op.create_index(
        "uq_sms_opt_outs_campaign",
        "sms_opt_outs",
        ["phone", "campaign_id"],
        unique=True,
        postgresql_where=sa.text("campaign_id IS NOT NULL"),
        sqlite_where=sa.text("campaign_id IS NOT NULL"),
    )
    op.create_index(
        "uq_sms_opt_outs_everywhere",
        "sms_opt_outs",
        ["phone"],
        unique=True,
        postgresql_where=sa.text("campaign_id IS NULL"),
        sqlite_where=sa.text("campaign_id IS NULL"),
    )

    op.create_table(
        "sms_inbound",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("to", sa.String(20), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        _created(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sms_inbound")),
        sa.UniqueConstraint("provider_id", name=op.f("uq_sms_inbound_provider_id")),
    )


def downgrade() -> None:
    op.drop_table("sms_inbound")
    op.drop_table("sms_opt_outs")
    op.drop_table("sms_log")
    op.drop_table("campaign_messages")
