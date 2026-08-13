"""notification_states.action: what was done from a nudge, not just to it

Read and dismissed were the only things a notification could record, because
they were the only things it could do. Now that a nudge can complete a habit or
push a task, the interaction history has a second side, and the back-off ladder
has a positive signal instead of only a negative one.

Plain ``op.add_column``: SQLite adds a nullable column in place, so the
table-rebuild hazard that ``batch_alter_table`` carries never arises here.
(See 03baa0cdd7f6 for the incident that rule comes from.)

Revision ID: c92d5f3a71e8
Revises: b71c4e0a9d52
Create Date: 2026-08-14 12:05:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c92d5f3a71e8"
down_revision: Union[str, None] = "b71c4e0a9d52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notification_states",
        sa.Column("action", sa.String(length=16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("notification_states", "action")
