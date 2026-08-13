"""email OTP verification: pending codes, and a proven-address stamp on users

Two changes:

* ``email_verifications`` — one row per code issued. Holds a salted scrypt hash
  of the code, never the code itself, plus everything needed to decide whether
  a guess should be honoured: expiry, attempts so far, and whether it has
  already been spent.
* ``users.email_verified_at`` — set when someone proves they can read the
  mailbox. Null means an address is on file but unproven.

Both use plain ``op.add_column`` / ``op.create_index`` rather than
``batch_alter_table``. Batch mode rebuilds a table as create/copy/drop/rename,
and ``auth_sessions`` holds an ON DELETE CASCADE foreign key to ``users`` — the
same shape that once silently deleted every habit_log when ``habits`` was
rebuilt. env.py disables foreign keys for the duration of a migration precisely
because of that, but SQLite adds a nullable column in place, so the question
never arises.

Revision ID: 03baa0cdd7f6
Revises: 14eb2d838d4f
Create Date: 2026-08-14 00:04:04.977846
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "03baa0cdd7f6"
down_revision: Union[str, None] = "14eb2d838d4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_verifications",
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("purpose", sa.String(length=16), nullable=False),
        sa.Column("otp_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        # SET NULL, not CASCADE: deleting an account should not erase the
        # record that a code was issued to that address.
        sa.Column("user_id", sa.String(length=32), nullable=True),
        sa.Column("request_ip", sa.String(length=64), nullable=True),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    # Both lookups the service makes on every request: the newest row for an
    # address, and the per-account history.
    op.create_index(
        "ix_email_verifications_email", "email_verifications", ["email"], unique=False
    )
    op.create_index(
        "ix_email_verifications_user_id", "email_verifications", ["user_id"], unique=False
    )

    op.add_column(
        "users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "email_verified_at")
    op.drop_index("ix_email_verifications_user_id", table_name="email_verifications")
    op.drop_index("ix_email_verifications_email", table_name="email_verifications")
    op.drop_table("email_verifications")
