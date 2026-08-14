# Atlas

> An intelligent, local-first second brain for habits, tasks, journaling, and life tracking — designed to learn from your behavior and get smarter over months of use.

Atlas is built to **never forget** your history (unless you explicitly delete it) and to turn that
history into evidence-backed recommendations. Everything runs locally by default; your data is yours.

## Status

Atlas is built **incrementally**, runnable at every phase. **Phases 1–11 are complete**, and
542 backend tests pass. See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the full plan and what remains.

- **A real desktop app** — Tauri shell, FastAPI backend bundled as a sidecar,
  one self-contained installer, tray, global hotkey, native notifications
  ([`docs/DESKTOP.md`](docs/DESKTOP.md))
- Habits, tasks, projects, journal, notes, calendar, focus mode, timeline
- Analytics, Life Score, weekly review, natural-language search
- **Analytics that say what they mean** — insight sentences with the arithmetic
  shown underneath, and a behaviour profile (when you work, which days hold, how
  long your runs last) that stays silent rather than guessing from thin evidence
- **ML layer** — completion model with rolling-origin evaluation, a second model
  for whether a task lands by its due date, prediction engine, smart scheduler,
  explainable recommendations, what-if simulator
- **Quick capture** — `gym tomorrow 7am !high` parses into a task, offline and
  deterministic; defer to tomorrow without moving the deadline; act on a
  notification instead of only reading it
- **AI Coach** — grounded in your own data; offline by default. Bring a key
  from Anthropic, Groq, Google Gemini or OpenRouter (the last three have free
  tiers), or run a local model through Ollama so nothing leaves the machine
- **Learning loops** — automatic retraining, notification back-off,
  recommendation-outcome tracking, model-quality history
- **Accounts** — sign in with a password, with Google (bring your own OAuth
  client), or with a code emailed to you (Resend, or free SMTP through an
  ordinary mailbox). scrypt hashes, revocable sessions, and a real per-account
  data partition ([`docs/SCOPING.md`](docs/SCOPING.md))
- **Obsidian sync** — journal and notes as plain Markdown in a vault folder,
  two-way, most recent edit wins
- Alembic migrations run at startup; client-side encrypted backup/restore, and
  **CSV export** — seven flat sheets to open in a spreadsheet, including a
  row-per-day join of what was due, what got done, and how you slept
- **Lite visual mode** for low-end hardware, chosen automatically

Still open: PostgreSQL adapter, Markdown/PDF export, optional cloud sync,
accessibility and i18n.

## Run Atlas

Atlas is a **desktop app** — you don't need a terminal to use it.

1. Install: run `release/atlas_setup.exe` (per-user, no admin prompt, works
   offline). Build it with `npm run release` from `frontend/`.
2. Launch from the **Desktop icon**, the **Start menu**, or `Ctrl + Shift + A`.

The backend is bundled and starts with the app. Closing the window hides Atlas to
the tray; quit properly from the tray menu. Full details — including how to
rebuild the installers — are in [`docs/DESKTOP.md`](docs/DESKTOP.md).

## Architecture

```
atlas/
├── backend/           FastAPI + SQLAlchemy + SQLite  (Python 3.12)
│   └── app/
│       ├── core/          config, logging, database engine/session
│       ├── domain/        enums + pure domain logic (no framework deps)
│       ├── models/        SQLAlchemy ORM models (persistence)
│       ├── schemas/       Pydantic DTOs (API contracts)
│       ├── repositories/  repository pattern over the ORM
│       ├── services/      business logic (streaks, analytics, dashboard)
│       ├── learning/      feature engineering, models, registry (optional import)
│       ├── migrations/    Alembic revisions, applied in-process at startup
│       ├── api/v1/        HTTP routers
│       └── db/            seed data
├── frontend/          React + TypeScript + Vite + Tailwind (warm editorial)
│   └── src-tauri/     Tauri desktop shell (tray, hotkey, sidecar lifecycle)
└── docs/              roadmap and design notes
```

Data flows one way: **API routers** depend on **services**, services depend on **repositories**,
repositories own the **ORM models**. Routers never touch the ORM directly. This is what lets the
ML layer read the full history without leaking persistence details everywhere.

## Develop

### Backend (Python 3.12)

```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
python -m app.db.seed          # optional: load demo data so the dashboard isn't empty
uvicorn app.main:app --reload  # http://127.0.0.1:8000  (docs at /docs)
```

### Frontend (Node 20+)

```bash
cd frontend
npm install
npm run dev                    # browser at http://127.0.0.1:5173
npm run tauri dev              # or the real desktop window
```

The frontend expects the backend at `http://127.0.0.1:8000` (override with `VITE_API_BASE`).
`npm run tauri dev` needs the Rust toolchain — see [`docs/DESKTOP.md`](docs/DESKTOP.md).

## Principles

- **Local-first & private.** SQLite on your machine; no telemetry, no tracking.
- **Never forget.** History is append-only where it matters (habit logs, journal, analytics).
- **Explainable.** Every recommendation ships with a reason and a confidence score.
- **Honest about thin evidence.** An insight with too little behind it is left out, not softened.
- **Runnable at every step.** Each phase leaves `master` in a working state.
