"""Party texts to members and volunteers, the Comms Officer, and members' SMS consent.

Revision ID: party_messages
Revises: campaign_sharing
Create Date: 2026-11-07 17:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "party_messages"
down_revision: str | None = "campaign_sharing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OFFICES_BEFORE = ("membership_officer", "nominations_officer")
OFFICES_AFTER = (*OFFICES_BEFORE, "comms_officer")


def _set_offices(*offices: str) -> None:
    """Replace the CHECK listing the party offices a login may hold.

    The old CHECK is looked up, as its name depends on how the table was first migrated.
    """
    allowed = "role IN (" + ", ".join(f"'{office}'" for office in offices) + ")"
    name = op.f("ck_party_roles_party_role")
    if op.get_context().as_sql:
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
    op.create_table(
        "party_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("audience", sa.String(20), nullable=False),
        sa.Column("county_id", sa.Uuid(), nullable=True),
        sa.Column("ward_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("drafted_by_id", sa.Uuid(), nullable=True),
        sa.Column("decided_by_id", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("targeted", sa.Integer(), nullable=False),
        sa.Column("recipients", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["county_id"],
            ["counties.id"],
            name=op.f("fk_party_messages_county_id_counties"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ward_id"],
            ["wards.id"],
            name=op.f("fk_party_messages_ward_id_wards"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["drafted_by_id"],
            ["users.id"],
            name=op.f("fk_party_messages_drafted_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_id"],
            ["users.id"],
            name=op.f("fk_party_messages_decided_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_party_messages")),
    )
    op.create_index(op.f("ix_party_messages_status"), "party_messages", ["status"])
    with op.batch_alter_table("sms_log") as batch:
        batch.add_column(sa.Column("party_message_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            op.f("fk_sms_log_party_message_id_party_messages"),
            "party_messages",
            ["party_message_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index(op.f("ix_sms_log_party_message_id"), ["party_message_id"])
    with op.batch_alter_table("party_members") as batch:
        batch.add_column(sa.Column("sms_consent_wording", sa.Text(), nullable=True))
        batch.add_column(sa.Column("sms_consent_at", sa.DateTime(timezone=True), nullable=True))
    _set_offices(*OFFICES_AFTER)


def downgrade() -> None:
    op.execute("DELETE FROM party_roles WHERE role = 'comms_officer'")
    _set_offices(*OFFICES_BEFORE)
    with op.batch_alter_table("party_members") as batch:
        batch.drop_column("sms_consent_at")
        batch.drop_column("sms_consent_wording")
    with op.batch_alter_table("sms_log") as batch:
        batch.drop_index(op.f("ix_sms_log_party_message_id"))
        batch.drop_constraint(
            op.f("fk_sms_log_party_message_id_party_messages"), type_="foreignkey"
        )
        batch.drop_column("party_message_id")
    op.drop_index(op.f("ix_party_messages_status"), table_name="party_messages")
    op.drop_table("party_messages")
