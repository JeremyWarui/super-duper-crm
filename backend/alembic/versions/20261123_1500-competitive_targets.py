"""Competitive targets: the campaign's turnout scenario and how each target was worked out.

Targets are reworked from past results by `campaign-crm seed-results`, which runs after this.

Revision ID: competitive_targets
Revises: election_results
Create Date: 2026-11-23 15:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "competitive_targets"
down_revision: str | None = "election_results"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum_check(table: str, enum: str) -> str:
    """The name an enum's CHECK carries: prefixed under the models' naming convention, bare
    otherwise."""
    target = op.get_context().opts.get("target_metadata")
    named = getattr(target, "naming_convention", {}).get("ck")
    return op.f(f"ck_{table}_{enum}" if named else enum)


def _choice(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True, length=20)


def _scenario() -> sa.Column:
    return sa.Column(
        "turnout_scenario",
        _choice("turnout_scenario", "low", "expected", "high"),
        server_default="expected",
        nullable=False,
    )


def upgrade() -> None:
    with op.batch_alter_table("campaigns") as batch:
        batch.add_column(_scenario())
        batch.add_column(sa.Column("turnout_scenario_set_by_id", sa.Uuid(), nullable=True))
        batch.add_column(
            sa.Column("turnout_scenario_set_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column("turnout_override_pct", sa.Numeric(precision=5, scale=2), nullable=True)
        )
        batch.create_foreign_key(
            op.f("fk_campaigns_turnout_scenario_set_by_id_users"),
            "users",
            ["turnout_scenario_set_by_id"],
            ["id"],
            ondelete="SET NULL",
        )
    with op.batch_alter_table("targets") as batch:
        batch.add_column(_scenario())
        batch.add_column(
            sa.Column(
                "turnout_overridden", sa.Boolean(), server_default=sa.false(), nullable=False
            )
        )
        batch.add_column(sa.Column("ward_weight", sa.Numeric(precision=11, scale=10)))
        batch.add_column(
            sa.Column(
                "reliability",
                _choice("target_reliability", "seat", "typical", "proxy"),
                server_default="proxy",
                nullable=False,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("targets") as batch:
        batch.drop_constraint(_enum_check("targets", "target_reliability"), type_="check")
        batch.drop_constraint(_enum_check("targets", "turnout_scenario"), type_="check")
        for column in ("reliability", "ward_weight", "turnout_overridden", "turnout_scenario"):
            batch.drop_column(column)
    with op.batch_alter_table("campaigns") as batch:
        batch.drop_constraint(_enum_check("campaigns", "turnout_scenario"), type_="check")
        batch.drop_constraint(
            op.f("fk_campaigns_turnout_scenario_set_by_id_users"), type_="foreignkey"
        )
        for column in (
            "turnout_override_pct",
            "turnout_scenario_set_at",
            "turnout_scenario_set_by_id",
            "turnout_scenario",
        ):
            batch.drop_column(column)
