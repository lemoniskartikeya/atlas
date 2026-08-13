"""plan_interactions: what the user did with what the planner suggested

One row per plan item per day, holding both the suggestion and the outcome, so
"you keep doing this in the evening" becomes something the app can read rather
than something only the user notices.

A new table only — nothing existing is touched, so there is no question of
``batch_alter_table`` rebuilding a table that something else holds an ON DELETE
CASCADE foreign key to. (See 03baa0cdd7f6 for why that matters here.)

Revision ID: b71c4e0a9d52
Revises: 03baa0cdd7f6
Create Date: 2026-08-14 11:20:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b71c4e0a9d52"
down_revision: Union[str, None] = "03baa0cdd7f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plan_interactions",
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("item_kind", sa.String(length=16), nullable=False),
        sa.Column("item_id", sa.String(length=32), nullable=False),
        sa.Column("suggested_block", sa.String(length=16), nullable=False),
        sa.Column("suggested_rank", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("actual_block", sa.String(length=16), nullable=True),
        sa.Column("at_hour", sa.Integer(), nullable=True),
        sa.Column("id", sa.String(length=32), nullable=False),
        # Nullable, like every other OwnedMixin table: a vault created before
        # accounts existed has no owner until the first account claims it.
        sa.Column("user_id", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "plan_date",
            "item_kind",
            "item_id",
            name="uq_plan_interaction_per_item_per_day",
        ),
    )
    op.create_index(
        op.f("ix_plan_interactions_action"), "plan_interactions", ["action"], unique=False
    )
    op.create_index(
        op.f("ix_plan_interactions_item_id"), "plan_interactions", ["item_id"], unique=False
    )
    op.create_index(
        op.f("ix_plan_interactions_plan_date"), "plan_interactions", ["plan_date"], unique=False
    )
    op.create_index(
        op.f("ix_plan_interactions_user_id"), "plan_interactions", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_plan_interactions_user_id"), table_name="plan_interactions")
    op.drop_index(op.f("ix_plan_interactions_plan_date"), table_name="plan_interactions")
    op.drop_index(op.f("ix_plan_interactions_item_id"), table_name="plan_interactions")
    op.drop_index(op.f("ix_plan_interactions_action"), table_name="plan_interactions")
    op.drop_table("plan_interactions")
