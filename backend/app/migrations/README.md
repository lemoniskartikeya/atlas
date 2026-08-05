# Migrations

Phase 1 uses `Base.metadata.create_all()` on startup for zero-friction local dev.
Alembic is wired here (env pulls the URL + metadata from the app) and becomes the
schema source of truth in Phase 7.

Generate the first migration once the schema settles:

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```
