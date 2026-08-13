"""Bring the database schema up to date at startup.

Alembic is the schema source of truth, but until now only the developer ever
ran it: the app called ``Base.metadata.create_all``, which creates *missing
tables* and nothing else. It cannot add a column to a table that already
exists, so a packaged install would silently drift — new tables would appear
while new columns on old tables never did, and the first query touching one
would 500.

This module runs the migrations the app actually needs, in-process, on every
start. It is idempotent: an up-to-date database is a no-op.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from app.core.config import RESOURCE_DIR, get_settings
from app.core.logging import get_logger

log = get_logger("atlas.schema")

# The first migration. A database created by the old create_all path carries no
# alembic_version, so it is stamped here before upgrading — otherwise Alembic
# would try to create tables that already exist.
BASELINE_REVISION = "f8d0c28e722c"


def _alembic_config(url: str):
    from alembic.config import Config

    cfg = Config(str(RESOURCE_DIR / "alembic.ini"))
    # Both are set explicitly: the .ini's relative script_location does not
    # resolve inside a frozen bundle, and the URL must be the one the app is
    # actually using (which may come from an env override).
    cfg.set_main_option("script_location", str(RESOURCE_DIR / "app" / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    # We are inside the running app, which configured logging at import. Read by
    # env.py: without this, Alembic's fileConfig would replace the root handler
    # and disable every logger the .ini does not name — muting the backend for
    # the rest of the process. Alembic's own logs still reach our JSON handler,
    # since they propagate to root like anything else.
    cfg.attributes["configure_logger"] = False
    return cfg


def upgrade_to_head(engine: Engine) -> str:
    """Apply pending migrations. Returns a short description of what happened."""
    from alembic import command

    settings = get_settings()
    cfg = _alembic_config(settings.database_url)

    tables = set(inspect(engine).get_table_names())
    fresh = not tables

    if not fresh and "alembic_version" not in tables:
        # Legacy database built by create_all: adopt it at the baseline so the
        # migrations that came after can apply on top.
        log.info("schema.stamping_legacy_database", extra={"revision": BASELINE_REVISION})
        command.stamp(cfg, BASELINE_REVISION)

    command.upgrade(cfg, "head")
    return "created" if fresh else "upgraded"


def ensure_schema(engine: Engine) -> None:
    """Best-effort schema upgrade. Never prevents the app from starting.

    A migration failure must not brick the app — the user still needs to reach
    Settings to export their data. The error is logged loudly instead.
    """
    try:
        outcome = upgrade_to_head(engine)
        log.info("schema.ready", extra={"outcome": outcome})
    except Exception as exc:  # pragma: no cover - depends on the DB's history
        log.error("schema.upgrade_failed", extra={"error": f"{type(exc).__name__}: {exc}"})
