"""Data protection: erasure marks, data requests, closing a campaign, and a withdrawal code for
every supporter.

Revision ID: data_protection
Revises: post_rich_text
Create Date: 2026-11-07 19:00:00.000000
"""

import secrets
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "data_protection"
down_revision: str | None = "post_rich_text"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ERASABLE = ("supporters", "volunteer_profiles", "party_members", "team_registrations")
SUPPORTERS = sa.table(
    "supporters", sa.column("id", sa.Uuid), sa.column("withdraw_code", sa.String)
)


def _give_codes() -> None:
    """Every supporter without a withdrawal code gets one; rendering SQL offline skips it."""
    if op.get_context().as_sql:
        return
    bind = op.get_bind()
    missing = bind.execute(
        sa.select(SUPPORTERS.c.id).where(SUPPORTERS.c.withdraw_code.is_(None))
    ).scalars()
    for supporter_id in list(missing):
        bind.execute(
            SUPPORTERS.update()
            .where(SUPPORTERS.c.id == supporter_id)
            .values(withdraw_code=secrets.token_urlsafe(18))
        )


def upgrade() -> None:
    for table in ERASABLE:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("erased_at", sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table("campaigns") as batch:
        batch.add_column(sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("closed_by_id", sa.Uuid(), nullable=True))
        batch.add_column(
            sa.Column("retention_months", sa.Integer(), server_default=sa.text("6"), nullable=False)
        )
        batch.add_column(
            sa.Column("supporters_erased_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.create_foreign_key(
            op.f("fk_campaigns_closed_by_id_users"),
            "users",
            ["closed_by_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_table(
        "data_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("requester_name", sa.String(150), nullable=False),
        sa.Column("requester_contact", sa.String(254), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("logged_by_id", sa.Uuid(), nullable=True),
        sa.Column("answered_by_id", sa.Uuid(), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "kind IN ('access', 'correction', 'erasure')",
            name=op.f("ck_data_requests_data_request_kind"),
        ),
        sa.CheckConstraint(
            "status IN ('open', 'done')", name=op.f("ck_data_requests_data_request_status")
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_data_requests_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["logged_by_id"],
            ["users.id"],
            name=op.f("fk_data_requests_logged_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["answered_by_id"],
            ["users.id"],
            name=op.f("fk_data_requests_answered_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_requests")),
    )
    op.create_index(op.f("ix_data_requests_campaign_id"), "data_requests", ["campaign_id"])
    _give_codes()


def downgrade() -> None:
    op.drop_index(op.f("ix_data_requests_campaign_id"), table_name="data_requests")
    op.drop_table("data_requests")
    with op.batch_alter_table("campaigns") as batch:
        batch.drop_constraint(op.f("fk_campaigns_closed_by_id_users"), type_="foreignkey")
        batch.drop_column("supporters_erased_at")
        batch.drop_column("retention_months")
        batch.drop_column("closed_by_id")
        batch.drop_column("closed_at")
    for table in ERASABLE:
        with op.batch_alter_table(table) as batch:
            batch.drop_column("erased_at")
