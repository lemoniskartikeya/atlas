"""multi-user data scoping: own every vault row

Accounts used to be an identity layer over one shared vault. This gives every
row of vault data an owner, and reworks the three constraints that assumed a
single tenant:

* ``journal_entries.date`` was globally unique — one account's entry for a day
  would have blocked every other account's.
* ``notification_states`` used the notification id as its primary key, but two
  accounts legitimately mint the same deterministic id on the same day.
* ``recommendation_outcomes`` was unique on ``(rec_id, shown_on)`` for the same
  reason.

Existing rows are backfilled to the earliest-created account. If there are no
accounts yet (a vault that has never been signed into), rows are left unowned
and the first account to register claims them — see
``AuthService.claim_orphan_vault``. That's deliberate: a migration inventing a
user would be worse than one that waits for a real one.

Revision ID: c4a1f9b73e02
Revises: 28ac7171f2a8
Create Date: 2026-08-08
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c4a1f9b73e02'
down_revision: Union[str, None] = '28ac7171f2a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#: Tables that only need the column added; the two with constraint surgery
#: (journal_entries, notification_states) are rebuilt explicitly below.
_SIMPLE_TABLES = [
    "habits",
    "habit_logs",
    "projects",
    "tasks",
    "notes",
    "focus_sessions",
    "job_runs",
]

_TIMESTAMPS = [
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
]


def _owner_column() -> sa.Column:
    return sa.Column("user_id", sa.String(length=32), nullable=True)


def _add_owner(table: str) -> None:
    with op.batch_alter_table(table) as batch:
        batch.add_column(_owner_column())
        batch.create_foreign_key(
            f"fk_{table}_user_id_users", "users", ["user_id"], ["id"], ondelete="CASCADE"
        )
    op.create_index(f"ix_{table}_user_id", table, ["user_id"])


def _drop_owner(table: str) -> None:
    op.drop_index(f"ix_{table}_user_id", table_name=table)
    with op.batch_alter_table(table) as batch:
        batch.drop_constraint(f"fk_{table}_user_id_users", type_="foreignkey")
        batch.drop_column("user_id")


def upgrade() -> None:
    bind = op.get_bind()

    for table in _SIMPLE_TABLES:
        _add_owner(table)

    # --- recommendation_outcomes: named constraint, so a batch swap is enough
    _add_owner("recommendation_outcomes")
    with op.batch_alter_table("recommendation_outcomes") as batch:
        batch.drop_constraint("uq_recommendation_shown_once_per_day", type_="unique")
        batch.create_unique_constraint(
            "uq_recommendation_shown_once_per_day", ["user_id", "rec_id", "shown_on"]
        )

    # --- journal_entries: the unique lives inline on `date` and is unnamed on
    # SQLite, so the table is rebuilt rather than fought with.
    op.create_table(
        "journal_entries_new",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("mood", sa.Integer(), nullable=True),
        sa.Column("energy", sa.Integer(), nullable=True),
        sa.Column("sleep_hours", sa.Float(), nullable=True),
        sa.Column("gratitude", sa.Text(), nullable=True),
        sa.Column("wins", sa.Text(), nullable=True),
        sa.Column("challenges", sa.Text(), nullable=True),
        sa.Column("free_writing", sa.Text(), nullable=True),
        sa.Column("reflection", sa.Text(), nullable=True),
        sa.Column("lessons", sa.Text(), nullable=True),
        *_TIMESTAMPS,
        _owner_column(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_journal_entries_user_id_users",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("user_id", "date", name="uq_journal_entry_user_date"),
    )
    op.execute(
        "INSERT INTO journal_entries_new (id, date, mood, energy, sleep_hours, "
        "gratitude, wins, challenges, free_writing, reflection, lessons, "
        "created_at, updated_at) "
        "SELECT id, date, mood, energy, sleep_hours, gratitude, wins, challenges, "
        "free_writing, reflection, lessons, created_at, updated_at "
        "FROM journal_entries"
    )
    op.drop_table("journal_entries")
    op.rename_table("journal_entries_new", "journal_entries")
    op.create_index("ix_journal_entries_date", "journal_entries", ["date"])
    op.create_index("ix_journal_entries_user_id", "journal_entries", ["user_id"])

    # --- notification_states: primary key changes from the notification id to
    # a surrogate, so this is a rebuild too. Ids are minted here rather than by
    # a DB default because SQLite has no uuid function.
    rows = list(
        bind.execute(
            sa.text(
                "SELECT notification_id, status, kind, target, created_at, updated_at "
                "FROM notification_states"
            )
        ).mappings()
    )
    op.drop_table("notification_states")
    op.create_table(
        "notification_states",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("notification_id", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=True),
        sa.Column("target", sa.String(length=64), nullable=True),
        *_TIMESTAMPS,
        _owner_column(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_notification_states_user_id_users",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "user_id", "notification_id", name="uq_notification_state_user_notification"
        ),
    )
    op.create_index(
        "ix_notification_states_notification_id", "notification_states",
        ["notification_id"],
    )
    op.create_index("ix_notification_states_kind", "notification_states", ["kind"])
    op.create_index("ix_notification_states_target", "notification_states", ["target"])
    op.create_index("ix_notification_states_user_id", "notification_states", ["user_id"])
    if rows:
        bind.execute(
            sa.text(
                "INSERT INTO notification_states "
                "(id, notification_id, status, kind, target, created_at, updated_at) "
                "VALUES (:id, :notification_id, :status, :kind, :target, "
                ":created_at, :updated_at)"
            ),
            [{**dict(row), "id": uuid.uuid4().hex} for row in rows],
        )

    # --- backfill ----------------------------------------------------------
    owner = bind.execute(
        sa.text("SELECT id FROM users ORDER BY created_at LIMIT 1")
    ).scalar()
    if owner is None:
        # No account exists: leave the vault unowned for the first registration
        # to claim. Nothing is lost, and nothing is guessed.
        return
    for table in _SIMPLE_TABLES + [
        "recommendation_outcomes",
        "journal_entries",
        "notification_states",
    ]:
        bind.execute(
            sa.text(f"UPDATE {table} SET user_id = :owner WHERE user_id IS NULL"),
            {"owner": owner},
        )


def downgrade() -> None:
    bind = op.get_bind()

    for table in _SIMPLE_TABLES:
        _drop_owner(table)

    with op.batch_alter_table("recommendation_outcomes") as batch:
        batch.drop_constraint("uq_recommendation_shown_once_per_day", type_="unique")
        batch.create_unique_constraint(
            "uq_recommendation_shown_once_per_day", ["rec_id", "shown_on"]
        )
    _drop_owner("recommendation_outcomes")

    # journal_entries: back to a globally unique date. Rows that would now
    # collide (two accounts with an entry for the same day) cannot survive a
    # single-tenant schema; keep the oldest and drop the rest rather than
    # failing the downgrade half-applied.
    op.execute(
        "DELETE FROM journal_entries WHERE id NOT IN ("
        "SELECT id FROM journal_entries GROUP BY date HAVING MIN(created_at))"
    )
    op.create_table(
        "journal_entries_old",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("mood", sa.Integer(), nullable=True),
        sa.Column("energy", sa.Integer(), nullable=True),
        sa.Column("sleep_hours", sa.Float(), nullable=True),
        sa.Column("gratitude", sa.Text(), nullable=True),
        sa.Column("wins", sa.Text(), nullable=True),
        sa.Column("challenges", sa.Text(), nullable=True),
        sa.Column("free_writing", sa.Text(), nullable=True),
        sa.Column("reflection", sa.Text(), nullable=True),
        sa.Column("lessons", sa.Text(), nullable=True),
        *_TIMESTAMPS,
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("date"),
    )
    op.execute(
        "INSERT INTO journal_entries_old SELECT id, date, mood, energy, sleep_hours, "
        "gratitude, wins, challenges, free_writing, reflection, lessons, "
        "created_at, updated_at FROM journal_entries"
    )
    op.drop_table("journal_entries")
    op.rename_table("journal_entries_old", "journal_entries")
    op.create_index("ix_journal_entries_date", "journal_entries", ["date"])

    # notification_states: back to the notification id as primary key, keeping
    # one row per id for the same reason.
    rows = list(
        bind.execute(
            sa.text(
                "SELECT notification_id, status, kind, target, created_at, updated_at "
                "FROM notification_states GROUP BY notification_id"
            )
        ).mappings()
    )
    op.drop_table("notification_states")
    op.create_table(
        "notification_states",
        sa.Column("notification_id", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=True),
        sa.Column("target", sa.String(length=64), nullable=True),
        *_TIMESTAMPS,
        sa.PrimaryKeyConstraint("notification_id"),
    )
    op.create_index("ix_notification_states_kind", "notification_states", ["kind"])
    op.create_index("ix_notification_states_target", "notification_states", ["target"])
    if rows:
        bind.execute(
            sa.text(
                "INSERT INTO notification_states "
                "(notification_id, status, kind, target, created_at, updated_at) "
                "VALUES (:notification_id, :status, :kind, :target, "
                ":created_at, :updated_at)"
            ),
            [dict(row) for row in rows],
        )
