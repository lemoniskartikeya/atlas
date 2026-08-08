# Multi-user data scoping

Atlas accounts used to be an *identity* layer: signing in told the app who you
were and gated the UI, but every account looked at the same habits, tasks and
journals. They are now a real partition. This is how it works and where the
sharp edges are.

## The rule

Every row of vault data belongs to exactly one account. A model becomes
account-scoped by inheriting `OwnedMixin` (`app/models/base.py`) — there is no
list of scoped tables to keep in sync, and `app.models.owned_models()` derives
the set from the mapper registry.

Currently owned: `habits`, `habit_logs`, `projects`, `tasks`, `journal_entries`,
`notes`, `focus_sessions`, `notification_states`, `recommendation_outcomes`,
`job_runs`.

## Three layers of enforcement

Relying on ~30 query sites to each remember `.where(user_id == me)` is how leaks
happen, so the identity lives on the **Session** and is enforced centrally.

1. **Session-wide filter** (`app/core/scoping.py`). A `do_orm_execute` event
   attaches `with_loader_criteria` over `OwnedMixin` to every ORM SELECT,
   including relationship and lazy loads. A new model is covered the moment it
   inherits the mixin.
2. **Write stamping.** A `before_flush` event stamps `user_id` on new rows, so
   create paths can't forget, and raises `ScopeError` if a row carries a
   *different* owner than the session is acting as.
3. **Explicit filters.** Repositories and services still name the owner in the
   queries they build (`BaseRepository.scoped()`). Deliberate duplication: the
   events are the safety net for the query someone writes next year.

An unbound session raises `ScopeError` rather than returning everything — a
loud failure beats a silent full-table read.

### What the filter does *not* cover

`with_loader_criteria` rewrites **SELECTs**. It does nothing for bulk
`DELETE`/`UPDATE`, which must filter by hand. There are exactly two:

- `BackupService.import_` wipes before restoring. Without its explicit
  `WHERE user_id = ...`, one account restoring a backup would erase every other
  account's vault. There is a test for this.
- `AuthService.claim_orphan_vault` updates `WHERE user_id IS NULL`, which by
  construction can only touch rows nobody owns.

`Session.get()` is also avoided in repositories: it consults the identity map
before emitting SQL and would hand back another account's row if the session had
already loaded it. `BaseRepository.get()` runs a real filtered SELECT instead.

## Where identity comes from

- **Requests** — `app.api.deps.scoped_session` resolves the bearer token and
  binds the account for the life of the request. Every service provider hangs
  off it, so all data endpoints 401 without a session. Only `/health` and
  `/auth/*` are public.
- **Background work** — the scheduler has no request to inherit from, so
  `jobs.run_due_for_all` walks every account with `acting_as()`. One account's
  failure is logged and skipped, not fatal to the tick.
- **CLI** — `python -m app.learning.train` trains every account (or one, by
  username); `python -m app.db.seed` seeds into the first account or `--user`.

## Per-account, not just the database

- **Models.** `data/models/<user_id>/` — a model only ever sees the logs of the
  account it was fitted on. A new account has no model and falls back to
  heuristics until it has enough history, which is the existing untrained path.
- **Job schedules.** `job_runs` is owned, so an idle account can't push out
  another's retrain.
- **Automatic backups.** `data/backups/<user_id>/`, because a shared folder
  would have each account's daily snapshot overwrite the last one to run.

## Upgrading an existing vault

The migration (`c4a1f9b73e02`) backfills every row to the **earliest-created
account**. If no account exists yet, rows are left unowned — invisible to
everyone — and the first account to register claims them
(`AuthService.claim_orphan_vault`). A migration that invented a user would be
worse than one that waits for a real one.

The same claim moves a pre-scoping model registry from `data/models/` into the
account's folder. Without it, upgrading would silently orphan a trained model
and the quality history would read as empty — indistinguishable from a bug.

### A SQLite trap worth remembering

Alembic's batch mode rebuilds a table as create-new / copy / **DROP old** /
rename. With foreign keys enforced (the app's connect hook turns them on), that
DROP cascades: rebuilding `habits` deleted all 226 `habit_logs`. `env.py` now
disables `PRAGMA foreign_keys` for the duration of a migration.

The pragma has to be the first statement on the connection — SQLite ignores it
inside a transaction — and the connection must then be committed, because any
execute autobegins a transaction and Alembic will not start its own on top of
one already open. Skipping that commit left the DDL applied (SQLite commits it
implicitly) but the `alembic_version` bump rolled back, so the migration
re-ran on next boot.

## Backups are portable

`user_id` is stripped on export and ignored on import: a backup is a document
about your data, not about which row in `users` owned it. Restoring into a
different account, or onto a fresh install, just works.

Row ids *do* travel, so a restore into an account where those ids are still
taken remaps them and rewrites every foreign key to match
(`BackupService._plan_ids`). Restoring your own vault keeps its ids, which is
what makes a restore idempotent.

## Known limits

- Accounts share one database file and one encryption boundary. This is a
  partition, not a security boundary against someone with disk access — the
  SQLite file is unencrypted, as it always has been.
- The Anthropic API key in `.env` is machine-level, shared by all accounts.
- Deleting an account cascades its data (`ondelete="CASCADE"`), but there is no
  UI for account deletion yet.
