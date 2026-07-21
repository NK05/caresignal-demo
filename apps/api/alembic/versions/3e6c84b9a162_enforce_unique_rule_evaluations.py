"""enforce unique rule evaluations

Revision ID: 3e6c84b9a162
Revises: 996314bc3c24
Create Date: 2026-07-17 21:01:24.740541
"""

from collections.abc import Sequence

from alembic import op

revision: str = "3e6c84b9a162"
down_revision: str | Sequence[str] | None = "996314bc3c24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("rule_evaluations") as batch_op:
        batch_op.create_unique_constraint(
            "uq_rule_evaluation_reading_rule_version",
            ["reading_id", "rule_id", "rule_version"],
        )


def downgrade() -> None:
    with op.batch_alter_table("rule_evaluations") as batch_op:
        batch_op.drop_constraint(
            "uq_rule_evaluation_reading_rule_version",
            type_="unique",
        )
