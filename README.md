# Atlas

> An intelligent, local-first second brain for habits, tasks, journaling, and life tracking — designed to learn from your behavior and get smarter over months of use.

Atlas is built to **never forget** your history (unless you explicitly delete it) and to turn that
history into evidence-backed recommendations. Everything runs locally by default; your data is yours.

## Status

Atlas is built **incrementally**, runnable at every phase. **Phases 1–9 are complete.**
See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the full plan and what remains.

- ✅ **A real desktop app** — Tauri shell, FastAPI backend bundled as a sidecar,
  MSI/NSIS installers, tray, global hotkey, native notifications
  ([`docs/DESKTOP.md`](docs/DESKTOP.md))
- ✅ Habits, tasks, projects, journal, notes, calendar, focus mode, timeline
- ✅ Analytics, Life Score, weekly review, natural-language search
- ✅ **ML layer** — completion model with rolling-origin evaluation, prediction
  engine, smart scheduler, explainable recommendations, what-if simulator
- ✅ **AI Coach** — grounded in your own data; offline by default, Claude API optional
- ✅ **Learning loops** — automatic retraining, notification back-off,
  recommendation-outcome tracking, model-quality history
- ✅ **Accounts** — scrypt passwords, revocable sessions, and a real per-account
  data partition ([`docs/SCOPING.md`](docs/SCOPING.md))
- ✅ Alembic migrations run at startup; client-side encrypted backup/restore

Still open: PostgreSQL adapter, CSV/Markdown/PDF export, optional cloud sync,
accessibility and i18n.

## Run Atlas

Atlas is a **desktop app** — you don't need a terminal to use it.

1. Install: run `frontend/src-tauri/target/release/bundle/nsis/Atlas_0.1.0_x64-setup.exe`
   (per-user, no admin prompt).
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
│       ├── api/v1/        HTTP routers
│       └── db/            seed data
├── frontend/          React + TypeScript + Vite + Tailwind (warm editorial)
│   └── src-tauri/     Tauri desktop shell (tray, hotkey, sidecar lifecycle)
└── docs/              roadmap and design notes
```

Data flows one way: **API routers** depend on **services**, services depend on **repositories**,
repositories own the **ORM models**. Routers never touch the ORM directly. This keeps the ML
layer (a future service) able to read history without leaking persistence details everywhere.

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
- **Explainable.** Every future recommendation ships with a reason and a confidence score.
- **Runnable at every step.** Each phase leaves `main` in a working state.
