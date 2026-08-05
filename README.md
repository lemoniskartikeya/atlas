# Atlas

> An intelligent, local-first second brain for habits, tasks, journaling, and life tracking — designed to learn from your behavior and get smarter over months of use.

Atlas is built to **never forget** your history (unless you explicitly delete it) and to turn that
history into evidence-backed recommendations. Everything runs locally by default; your data is yours.

## Status

Atlas is being built **incrementally**, keeping the app runnable at every phase. See
[`docs/ROADMAP.md`](docs/ROADMAP.md) for the full plan and what is done vs. pending.

**Phase 1 (current): Foundation + working vertical slice**
- ✅ Clean-architecture FastAPI backend (domain → repository → service → API)
- ✅ SQLite persistence via SQLAlchemy 2.0, resilient startup, seed data
- ✅ Habits, Tasks, Journal, Dashboard, and Analytics (heatmap) APIs
- ✅ Streak / consistency / success-rate engine with unit tests
- ✅ Glassmorphism React + TypeScript frontend (dashboard + habit tracking)

The heavy features from the spec — the ML learning layer, AI coach, smart scheduler,
prediction engine, and Tauri desktop packaging — are scoped as later phases in the roadmap,
built on top of this foundation.

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
├── frontend/          React + TypeScript + Vite + Tailwind (glassmorphism)
└── docs/              roadmap and design notes
```

Data flows one way: **API routers** depend on **services**, services depend on **repositories**,
repositories own the **ORM models**. Routers never touch the ORM directly. This keeps the ML
layer (a future service) able to read history without leaking persistence details everywhere.

## Quick start

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
npm run dev                    # http://127.0.0.1:5173
```

The frontend expects the backend at `http://127.0.0.1:8000` (override with `VITE_API_BASE`).

## Principles

- **Local-first & private.** SQLite on your machine; no telemetry, no tracking.
- **Never forget.** History is append-only where it matters (habit logs, journal, analytics).
- **Explainable.** Every future recommendation ships with a reason and a confidence score.
- **Runnable at every step.** Each phase leaves `main` in a working state.
