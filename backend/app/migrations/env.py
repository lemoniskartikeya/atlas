"""Alembic environment. Pulls the URL + metadata from the Atlas app itself."""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context

import app.models  # noqa: F401  -- register all tables on Base.metadata
from app.core.config import get_settings
from app.core.database import engine
from app.models.base import Base

config = context.config
# Only the `alembic` CLI gets to configure logging. The app runs migrations
# in-process at startup (core/schema.py) and owns its own logging: fileConfig
# replaces the root handler and, worse, DISABLES every logger the .ini does not
# name — which is every uvicorn.* and atlas.* logger. That silenced the packaged
# backend a few seconds into every launch, so nothing after startup was ever
# recorded. `configure_logger` is Alembic's own escape hatch for programmatic
# use; disable_existing_loggers=False keeps even the CLI path from doing it.
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    try:
        fileConfig(config.config_file_name, disable_existing_loggers=False)
    except Exception:  # pragma: no cover - logging config is best-effort
        pass

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite-friendly ALTERs
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        sqlite = connection.dialect.name == "sqlite"
        if sqlite:
            # SQLite cannot ALTER most things, so Alembic's batch mode rebuilds
            # a table as create-new / copy / DROP old / rename. With foreign
            # keys enforced (the app's connect hook turns them on), that DROP
            # cascades: rebuilding `habits` silently deleted every `habit_log`.
            # Enforcement is off only for the duration of the migration, and
            # the pragma must be the first statement on the connection because
            # SQLite ignores it inside a transaction.
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            # Any execute autobegins a transaction, and Alembic will not start
            # its own on top of one already open — leaving its version bump
            # uncommitted while the DDL (which SQLite commits implicitly) went
            # through. Close it here so the stamp lands with the schema.
            connection.commit()
        try:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                render_as_batch=True,
            )
            with context.begin_transaction():
                context.run_migrations()
        finally:
            if sqlite:
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
