"""add conversation provider fields

Revision ID: b5f7d11e04c2
Revises: 3e6c84b9a162
Create Date: 2026-07-18 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b5f7d11e04c2"
down_revision: str | Sequence[str] | None = "3e6c84b9a162"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

generation_type = sa.Enum(
    "fixed_template",
    "ai_draft",
    "clinician_authored",
    name="generation_type",
    native_enum=False,
    create_constraint=True,
)
approval_status = sa.Enum(
    "draft",
    "approved",
    "sent",
    "rejected",
    name="approval_status",
    native_enum=False,
    create_constraint=True,
)


def upgrade() -> None:
    with op.batch_alter_table("patient_messages") as batch_op:
        batch_op.alter_column(
            "generation_type",
            existing_type=generation_type,
            nullable=True,
        )
        batch_op.alter_column(
            "approval_status",
            existing_type=approval_status,
            nullable=True,
        )
        batch_op.add_column(sa.Column("provider_message_id", sa.String(length=160)))
        batch_op.create_unique_constraint(
            "uq_patient_messages_provider_message_id",
            ["provider_message_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("patient_messages") as batch_op:
        batch_op.drop_constraint(
            "uq_patient_messages_provider_message_id",
            type_="unique",
        )
        batch_op.drop_column("provider_message_id")
        batch_op.alter_column(
            "approval_status",
            existing_type=approval_status,
            nullable=False,
        )
        batch_op.alter_column(
            "generation_type",
            existing_type=generation_type,
            nullable=False,
        )
