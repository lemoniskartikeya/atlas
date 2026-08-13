# Migrations

Alembic is the schema source of truth as of Phase 7. `env.py` pulls the database
URL and `target_metadata` straight from the app, so migrations always track the
ORM models in `app/models/`.

Local dev still calls `Base.metadata.create_all()` on startup for zero-friction
first run. That is convenient but **not** a substitute for migrations: once a DB
exists, schema changes must go through Alembic so the change is captured, ordered,
and reversible.

Run all commands from `backend/` with the venv active.

## Common commands

```bash
# Show the current revision of the configured DB
alembic current

# Apply all pending migrations
alembic upgrade head

# Create a new migration after changing models in app/models/
alembic revision --autogenerate -m "describe the change"
#   ^ review the generated file before committing — autogenerate is a draft,
#     not gospel (it can miss server-side defaults, CHECK constraints, renames).

# Roll back one revision / all the way down
alembic downgrade -1
alembic downgrade base

# Fail (non-zero exit) if models and migrations have drifted apart — CI-friendly
alembic check
```

## Adopting Alembic on an existing DB

A database created by `create_all()` already has every table but no
`alembic_version` row, so Alembic thinks it is at "base". Mark it as current
(records the version without re-running DDL) instead of upgrading:

```bash
alembic stamp head
```

The bundled dev `atlas.db` was stamped at the baseline revision
(`f8d0c28e722c`, "initial schema"), so `alembic upgrade head` on it is a no-op
and future migrations apply on top.

## Pointing at a different database

`env.py` reads the URL from Settings, which honors `ATLAS_DATABASE_URL`. To run a
migration against a throwaway DB (e.g. to regenerate the baseline from empty):

```bash
ATLAS_DATABASE_URL="sqlite:///./scratch.db" alembic upgrade head
```

## Logging (env.py runs inside the app)

Migrations run in-process on every startup (`app/core/schema.py`), so `env.py`
must not touch the logging the app already configured. `logging.config.fileConfig`
replaces the root handler *and disables every logger this `.ini` does not name* —
which is all of `uvicorn.*` and `atlas.*`. That muted the packaged backend a few
seconds into every launch, and the desktop log lost everything after boot.

So `env.py` only configures logging when Alembic's `configure_logger` attribute
is left at its default, and passes `disable_existing_loggers=False` regardless.
`schema.py` sets `cfg.attributes["configure_logger"] = False` for the in-process
path; the `alembic` CLI still gets the console formatting from this `.ini`.
`tests/test_schema.py` fails if either half regresses.
