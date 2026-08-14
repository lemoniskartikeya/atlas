# Atlas — Development Roadmap

Atlas is large. This roadmap breaks it into phases that each leave the app **fully runnable**.
Every phase builds on the clean-architecture foundation so the later intelligence features (ML,
coach, scheduler) can read the full history without rework.

Each phase heading carries its state. Within a phase, an unmarked bullet is done; anything still
outstanding is marked **Open**, and anything decided against is marked **Dropped** with the reason.

**Where things stand:** Phases 1–11 are complete. 542 backend tests pass; the desktop app ships as
a single installer. What remains is listed under [Still open](#still-open) — none of it blocks
daily use.

---

## Phase 1 — Foundation & vertical slice  (complete)
Goal: a real, running app you can use daily for habits, tasks, and journaling.

- Monorepo, tooling, docs, roadmap
- Backend clean architecture (core / domain / models / schemas / repositories / services / api)
- SQLite + SQLAlchemy 2.0, resilient startup, structured logging, settings
- Domain models: Habit, HabitLog, Task, Project, JournalEntry, Note
- Habit engine: completion/skip/partial logging, streaks, longest streak, consistency, success %
- REST API: habits, habit logs, tasks, journal, dashboard, analytics (year heatmap), health
- Seed data (30+ days of realistic history) so analytics/ML have something to chew on
- Unit tests for the streak/consistency engine + API smoke tests
- Frontend: design system, light/dark auto theme, dashboard, habit tracking
- Frontend: task board + daily journal editor

## Phase 2 — Full task & journal surfaces  (complete)

- Projects, subtasks, tags/labels, effort estimates, context/energy/focus metadata
- Calendar (month grid with per-day habits, tasks, journal and focus; day-detail panel)
- Rich journal — gratitude, wins, challenges, lessons, reflection, free writing
- Notes: markdown, tags, search
- **Dropped:** attachments (photos, voice, files) — a local-first vault that swallows binaries
  becomes a backup problem; Obsidian sync (Phase 10) covers the "keep files alongside my notes"
  case better
- **Dropped:** recurring tasks — habits already model recurrence properly; a second, weaker
  recurrence engine on tasks would compete with them
- **Dropped:** task dependencies, drag-and-drop scheduling, note backlinks — real features, no
  demand yet

## Phase 3 — Analytics & Life Score  (complete)

- GitHub-style yearly contribution heatmap, weekly/monthly productivity, personal bests
- Habit correlation graphs (mood vs. productivity, sleep vs. focus, exercise vs. focus)
- Composite **Life Score** with trend lines (not judgment), hover-anywhere day-in-context readings
- **Open:** monthly report as PDF — see [Still open](#still-open)

## Phase 4 — Machine Learning layer  (complete)
Built as a `learning` package over the historical feature store, imported optionally so the base
app stays lightweight.

- Leakage-safe feature engineering (every feature computable at the moment the outcome was decided)
- Habit completion model — HistGradientBoosting over 22 features, 8 of them carrying history
- **Rolling-origin evaluation** across four cut points, reporting the fold spread rather than a
  single flattering number, plus the minority-class count that limits how far to trust it
- Model registry: per-account, versioned, keyed by model kind, with automatic retraining jobs
- Explainability — permutation importances behind every prediction's plain-English "why"
- **Dropped:** XGBoost / LightGBM — an extra native dependency in the installer for no measurable
  gain on a few hundred rows
- **Dropped:** Prophet / statsmodels forecasting for energy and sleep — the same objection, and a
  personal tracker never has the seasons of data those models want

## Phase 5 — Recommendation, Prediction & Scheduler  (complete)

- Morning brief + recommendation engine (confidence + reason on every item)
- Prediction engine: completion likelihood, streak-break risk, transparent burnout signal
- Smart scheduler — "Today's Plan", blocks ordered so the shakiest items surface first
- Smart notifications: time-gated, derived fresh, and they back off when ignored (Phase 9)

## Phase 6 — Intelligence surfaces  (complete)

- AI Coach — grounded in a digest of your own numbers; offline by default
- Habit simulator — model-grounded "what if I slept an hour more?", with per-habit deltas
- Weekly review — a narrative recap generated locally, week against week
- Natural-language global search ("What did I do last Friday?") — rule-based, transparent, local
- Timeline view across habits, streak milestones, tasks, journal and focus

## Phase 7 — Platform & hardening  (complete)

- **Real desktop app** — PyInstaller sidecar backend, MSI/NSIS installers, custom
  titlebar, window-state persistence, system tray, global hotkey, native
  notifications, launch-at-login (see `docs/DESKTOP.md`)
- Alembic-managed migrations as the source of truth, run in-process at startup so an
  installed copy upgrades itself
- Encrypted backups (AES-GCM/PBKDF2, client-side) + JSON export/restore
- CSV export — seven sheets including a `daily` join no table holds (Phase 11)
- Focus mode (Pomodoro/deep-work timer, distraction counter)
- **Background job scheduler** — in-process asyncio loop, schedule computed from
  persisted run history, running automatic retraining + daily backups
- **Open:** PostgreSQL adapter, Markdown/PDF export, optional cloud sync, accessibility, i18n

## Phase 8 — Accounts, identity & polish  (complete)

- **Atlas accounts** — scrypt-hashed passwords, revocable opaque sessions,
  register/login/logout/change-password, first-run setup, username on the dashboard.
  Password policy: at least 8 characters with a letter, a number, and a special character.
- **Warm editorial design system** — new palette, serif display type, reworked
  glass material, and a shared motion vocabulary (press, lift, stagger, draw-on
  ticks, completion ring)
- **Interactive life-score chart** — hover anywhere across the plot, compact
  tooltip, continuous day-in-context insights
- **Completion history** — `GET /tasks/completed`, throughput chart, archive
  grouped by day; completing a task plays an exit animation instead of vanishing
- **Conversational AI Coach** — answers general questions, not just Atlas
  intents; API key managed in-app and stored locally
- **Multi-user data scoping** — accounts are a real partition, not just a lock.
  Every vault row carries an owner, every data endpoint requires a session, and
  each account gets its own model, job schedule and backups. See `docs/SCOPING.md`.

## Phase 9 — Closing the learning loops  (complete)
Atlas could always *predict*. This phase is what makes it actually improve with use.

- **Automatic retraining** — the model no longer waits for a manual CLI run.
  Gated on new-evidence volume, so it refits when there's something to learn from.
  A brand-new account re-checks every three hours until it has a model, rather than
  spending its first fortnight with every smart feature silently switched off.
- **Notification back-off** — repeated dismissals of the same nudge silence it
  for a growing cooldown; a single open resets it. Delivers the Phase 5 promise
  ("back off when ignored") that was previously only half-built.
- **Recommendation outcome tracking** — every suggestion shown is recorded and
  resolved the next day against what actually happened; families that work for
  this user rank higher. Atlas learns from its own advice.
- **Model-quality history** — accuracy and corpus size per version, so a
  retrain that *hurts* is visible rather than silent — and a swing that is only
  noise is reported as no measurable change rather than painted red.
- All four surfaced in Settings → Learning, so "how am I getting better" is
  answerable from inside the app.

## Phase 10 — Production, identity & integrations  (complete)
Making Atlas something a person other than its author can install and sign in to.

- **One-file installer** — `npm run release` produces `release/atlas_setup.exe`: app,
  bundled backend and WebView2 bootstrapper in a single per-user setup, no admin prompt
- **The coach is multi-provider** — Anthropic (paid), Groq and Google Gemini (real free
  tiers), OpenRouter (genuinely free models), or **Ollama on this machine, no key, nothing
  leaves the device**. Keys stored one per provider; every failure falls back to the
  offline answer and says where the answer came from
- **Sign in with Google** — OAuth 2.0 + PKCE through the real browser, loopback redirect.
  Accounts matched on Google's `sub`, never the email; an existing vault is linked only when
  Google says the address is verified. Bring your own client ID — a credential cannot ship
  inside a binary anyone can read
- **Sign in with an emailed code** — the same opaque revocable session as every other path.
  Only a salted scrypt hash of the code is stored, 10-minute expiry, 5 attempts, consumed on
  use, and rate limits counted from the rows so a restart cannot reset them
- **Free SMTP sender** — a Gmail App Password delivers real codes with no domain and no paid
  plan; Resend stays supported. Pinning a provider that is not configured sends nothing rather
  than quietly using the other one
- **Two-way Obsidian sync** — journal and notes as plain Markdown in an `Atlas` folder inside
  your vault. No plugin. `atlas_id` in frontmatter survives renames, hand-written files are
  imported, and when the vault's copy is newer Atlas refuses to overwrite it and *says so*
- **Lite effects mode** — `backdrop-filter` and the aurora dropped on low-end hardware,
  chosen automatically before first paint; the aurora's drift is translate-only, because
  animating `scale` on a 52px blur re-rasterizes it every frame
- **Fewer boxes** — sections default to a flat surface, the dashboard is about today (eight
  cards to four, nothing deleted — moved to where you'd look for it), less copy
- **It says why it didn't start** — a sidecar that dies is reported with its own last line and,
  for the common case, names the port and what to do about it, instead of a splash that spins
  for 25 seconds and guesses
- **The desktop log actually logs** — `fileConfig` had been disabling every logger three
  seconds into each launch; window controls work and report their failures; the titlebar reports
  its own geometry, which is how both bugs were found

## Phase 11 — Judgement, and getting things in  (complete)
Atlas could show you everything and tell you almost nothing. This phase is about what the data
*means*, and about making it cheap to put data in.

- **The analytics page says what it means, in sentences** — six rules over the charts already
  there, each carrying the arithmetic underneath so the claim can be checked rather than trusted.
  Every rule has a minimum sample and a minimum effect and returns nothing below either
- **A behaviour profile** — the hours completions land in, which weekdays hold, how long runs
  last before they break, and what a crowded day does to output. Stable traits, not this week's
  weather, and absent rather than invented when the evidence is thin. The coach gets them too
- **The ML layer knows about tasks** — a second model asking a different question: will this
  land by its due date? Undated and cancelled tasks are excluded on purpose. Deadline risk
  reaches the Plan page through the existing pattern — the model when trained, your own on-time
  rate otherwise, and silence when there is no basis for either
- **The planner notices when you disagree with it** — three completions in the same "wrong"
  block move the item, and it says why. One correction moves nothing; a split record moves
  nothing; evidence older than two months stops counting
- **Defer a task to tomorrow without moving its deadline** — a task pushed past its due date
  stays overdue and keeps saying so. A tracker that resolved late items by sliding the date
  would be worse than one with no defer button at all
- **`gym tomorrow 7am !high` is a task** — dates, times, priority, effort and #tags parsed out
  of the title field. Deterministic and offline; no model is called. It shows what it read
  before applying it, and never overrules a field you touched
- **Notifications can be dealt with, not just read** — complete or defer an overdue task, log a
  slipping habit, or say "not now", from the nudge. Informational nudges offer nothing, because
  there is nothing to do about them. What you did is recorded, so back-off can finally learn that
  a nudge *worked* and not only that it was ignored
- **CSV export** — seven flat sheets for opening, not restoring, including `daily`: a row per
  day with what was due, what got done, and how you slept. BOM for Excel, and formula-leading
  cells are neutralised rather than exported as something that executes
- **A habit is no longer counted as missed before it existed** — the per-day frame asked only
  whether a habit recurs on a day, never whether it had been created yet, so a habit kept
  perfectly for three weeks read as 6%. Fixed at the frame, which corrects weekly productivity,
  the correlations, the insights, the behaviour profile and the daily CSV at once

---

## Still open

Nothing here blocks daily use; each is a deliberate "not yet", not an oversight.

- **PostgreSQL adapter** — SQLite is right for a local-first desktop app. This matters only
  if Atlas ever runs as a shared server.
- **Markdown and PDF export** — CSV covers the analysis case and Obsidian sync covers the
  Markdown one; a monthly PDF report is the remaining gap.
- **Optional cloud sync** — the honest version is end-to-end encrypted and account-owned.
  Backups plus Obsidian sync cover most of what people actually want from it.
- **Accessibility** — keyboard paths and the command palette are good; a real audit
  (focus order, screen-reader labels, contrast at every state, reduced-motion coverage)
  has not been done.
- **i18n** — all copy is English and hard-coded.
- **Per-habit models** and learned burnout thresholds — one global model does the work today;
  the burnout formula is deliberately a documented weighted sum rather than something fitted.
- **Coach memory across conversations** — every turn starts from a fresh digest.

---

## Working agreement
- Each feature must be **functional before moving on** — no broad stubs.
- Backend changes ship with tests; the streak/analytics/ML math is always tested.
- Every recommendation is **explainable** (reason + confidence), never a black box.
- History is **append-only** where it matters; nothing is deleted without an explicit user action.
- Anything derived from thin evidence **says nothing at all** rather than saying something
  plausible — no horoscopes.
