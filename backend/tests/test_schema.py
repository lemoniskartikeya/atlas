"""The startup migration must not take the app's logging down with it.

Alembic's ``env.py`` calls ``logging.config.fileConfig``, which by default
*disables every logger the .ini does not name* and replaces the root handler.
Running that in-process at startup muted the packaged backend a few seconds into
every launch: no "startup complete", no job runs, no errors — the desktop log
(the first place anyone looks) simply stopped. These tests pin the fix.
"""
from __future__ import annotations

import logging
from types import SimpleNamespace

import sqlalchemy as sa

from app.core import database, schema
from app.core.logging import configure_logging

# Loggers that exist by the time migrations run at real startup.
PROBE_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access", "atlas.jobs")


def test_in_process_migrations_keep_app_logging_alive(tmp_path, monkeypatch):
    db_url = f"sqlite:///{(tmp_path / 'schema_probe.db').as_posix()}"
    engine = sa.create_engine(db_url)
    # env.py migrates app.core.database.engine; upgrade_to_head reads the URL
    # from settings. Point both at the throwaway database.
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(schema, "get_settings", lambda: SimpleNamespace(database_url=db_url))

    root = logging.getLogger()
    saved_handlers, saved_level = list(root.handlers), root.level
    try:
        configure_logging(False)
        for name in PROBE_LOGGERS:
            logging.getLogger(name)
        handlers_before, level_before = list(root.handlers), root.level

        schema.ensure_schema(engine)

        # The migration really ran — otherwise this test would pass vacuously,
        # since ensure_schema swallows failures by design.
        tables = set(sa.inspect(engine).get_table_names())
        assert {"alembic_version", "habits", "habit_logs", "users"} <= tables

        assert root.handlers == handlers_before, "root logging handler was replaced"
        assert root.level == level_before, "root log level was changed"
        for name in PROBE_LOGGERS:
            assert not logging.getLogger(name).disabled, f"{name} was disabled"

        # The app's own loggers still emit after the upgrade.
        records: list[logging.LogRecord] = []
        probe = logging.Handler()
        probe.emit = records.append  # type: ignore[method-assign]
        root.addHandler(probe)
        try:
            logging.getLogger("atlas.jobs").info("jobs.tick")
        finally:
            root.removeHandler(probe)
        assert [r.getMessage() for r in records] == ["jobs.tick"]
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)
        for name in PROBE_LOGGERS:
            logging.getLogger(name).disabled = False
        engine.dispose()


def test_alembic_config_opts_out_of_logging_config():
    """The contract env.py reads. The `alembic` CLI still configures logging."""
    cfg = schema._alembic_config("sqlite://")
    assert cfg.attributes["configure_logger"] is False
