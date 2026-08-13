"""google sign-in: identify a linked account by Google's stable subject id

Adds `users.google_sub`. Deliberately NOT a batch_alter_table: batch mode
rebuilds the table (create / copy / drop / rename), and `auth_sessions` holds
an ON DELETE CASCADE foreign key to `users` — the same shape that silently
deleted every habit_log when `habits` was rebuilt during the scoping migration.
env.py disables foreign keys for the duration of a migration precisely because
of that, but a plain ADD COLUMN sidesteps the question entirely. SQLite
supports adding a nullable column and creating an index in place.

Revision ID: 14eb2d838d4f
Revises: c4a1f9b73e02
Create Date: 2026-08-13 23:17:06.514377
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "14eb2d838d4f"
down_revision: Union[str, None] = "c4a1f9b73e02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_sub", sa.String(length=64), nullable=True))
    # Unique so one Google account cannot end up attached to two Atlas
    # accounts. NULLs don't collide in SQLite, so every password-only account
    # stays valid.
    op.create_index("ix_users_google_sub", "users", ["google_sub"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_google_sub", table_name="users")
    op.drop_column("users", "google_sub")
