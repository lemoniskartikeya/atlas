# Atlas — Development Roadmap

Atlas is large. This roadmap breaks it into phases that each leave the app **fully runnable**.
Every phase builds on the clean-architecture foundation so later intelligence features (ML, AI
coach, scheduler) can read the full history without rework.

Legend: ✅ done · 🚧 in progress · ⬜ planned

---

## Phase 1 — Foundation & vertical slice  🚧
Goal: a real, running app you can use daily for habits, tasks, and journaling.

- ✅ Monorepo, tooling, docs, roadmap
- ✅ Backend clean architecture (core / domain / models / schemas / repositories / services / api)
- ✅ SQLite + SQLAlchemy 2.0, resilient startup, structured logging, settings
- ✅ Domain models: Habit, HabitLog, Task, Project, JournalEntry, Note
- ✅ Habit engine: completion/skip/partial logging, streaks, longest streak, consistency, success %
- ✅ REST API: habits, habit logs, tasks, journal, dashboard, analytics (year heatmap), health
- ✅ Seed data (30+ days of realistic history) so analytics/ML have something to chew on
- ✅ Unit tests for the streak/consistency engine + API smoke tests
- 🚧 Frontend: glass design system, light/dark auto theme, dashboard, habit tracking
- ⬜ Frontend: task board + daily journal editor

## Phase 2 — Full task & journal surfaces  ⬜
- Projects, subtasks, dependencies, recurring tasks, tags/labels, calendar (day/week/month/agenda)
- Drag-and-drop scheduling
- Rich journal (gratitude/wins/challenges/reflection) + attachments (photos, voice, files)
- Notes: markdown, backlinks, tags, daily notes, global search

## Phase 3 — Analytics & Life Score  ⬜
- GitHub-style yearly contribution heatmap, weekly/monthly productivity, personal bests
- Habit correlation graphs (mood vs. productivity, sleep vs. focus, exercise vs. focus)
- Composite **Life Score** with trend lines (not judgment)
- Monthly report (PDF export)

## Phase 4 — Machine Learning layer  ⬜
The core differentiator. Built as a `learning` service package over the historical feature store.
- Feature engineering pipeline + persisted feature store (append-only)
- Models: Gradient Boosting / Random Forest / XGBoost / LightGBM for completion & skip prediction
- Time-series forecasting (Prophet/statsmodels) for energy, sleep, productivity trends
- Model registry: versioning, automatic retraining jobs, accuracy evaluation
- Explainability (feature attributions) so every prediction has a "why"

## Phase 5 — Recommendation, Prediction & Scheduler  ⬜
- Morning brief + recommendation engine (confidence + reason on every item)
- Prediction engine: completion likelihood, streak-break risk, burnout risk, expected focus/energy
- Smart scheduler: reorder tasks by energy/focus/deadline/context-switch cost; one-click optimize
- Smart notifications: fire only when success is likely; back off when ignored

## Phase 6 — Intelligence surfaces  ⬜
- AI Coach (retrieval over your history + learned models → evidence-backed answers)
- Habit simulator ("what if I sleep 1h more / exercise 5×/week / drop caffeine?")
- Weekly AI review, habit relationship discovery, habit suggestions
- Natural-language global search ("What did I do last Friday?", "When was I happiest?")
- Timeline view across all data types

## Phase 7 — Platform & hardening  ⬜
- Tauri desktop packaging (requires Rust + MSVC toolchain + WebView2)
- Alembic-managed migrations as source of truth; PostgreSQL adapter
- Encrypted backups, export (JSON/CSV/Markdown/PDF), optional cloud sync
- Focus mode (Pomodoro/deep-work timer, distraction counter), accessibility, i18n
- Background job scheduler for retraining + backups

---

## Working agreement
- Each feature must be **functional before moving on** — no broad stubs.
- Backend changes ship with tests; the streak/analytics/ML math is always tested.
- Every recommendation is **explainable** (reason + confidence), never a black box.
- History is **append-only** where it matters; nothing is deleted without an explicit user action.
