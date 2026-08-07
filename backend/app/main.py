"""Atlas FastAPI application entrypoint."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401  -- ensure every table is registered on Base.metadata
from app.api.v1 import (
    analytics,
    auth,
    backup,
    calendar,
    coach,
    dashboard,
    feedback,
    focus,
    habits,
    jobs,
    journal,
    ml_history,
    notifications,
    planner,
    predictions,
    review,
    search,
    simulator,
    tasks,
    timeline,
)
from app.core.config import get_settings
from app.core.database import engine
from app.core.logging import configure_logging, get_logger
from app.models.base import Base

settings = get_settings()
configure_logging(settings.debug)
log = get_logger("atlas")

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Dev convenience: ensure tables exist. Alembic becomes source of truth later.
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
        log.info("startup.tables_ensured", extra={"database_url": settings.database_url})

    task = None
    if settings.jobs_enabled:
        from app.core.database import SessionLocal
        from app.services.jobs import scheduler_loop

        task = asyncio.create_task(scheduler_loop(SessionLocal))
        log.info("startup.scheduler_started")

    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            # Await the cancellation so the loop's `finally` blocks run and the
            # session is closed before the process exits.
            try:
                await task
            except asyncio.CancelledError:
                pass
            log.info("shutdown.scheduler_stopped")


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for router in (
        auth.router,
        calendar.router,
        jobs.router,
        ml_history.router,
        feedback.router,
        habits.router,
        tasks.router,
        journal.router,
        dashboard.router,
        analytics.router,
        planner.router,
        predictions.router,
        notifications.router,
        simulator.router,
        review.router,
        timeline.router,
        search.router,
        coach.router,
        focus.router,
        backup.router,
    ):
        app.include_router(router, prefix=API_PREFIX)

    # ML endpoints are optional — the app still runs if the ML deps aren't installed.
    try:
        from app.api.v1 import ml

        app.include_router(ml.router, prefix=API_PREFIX)
    except Exception as exc:  # pragma: no cover - depends on optional install
        log.warning("ml.router_unavailable", extra={"error": str(exc)})

    @app.get(f"{API_PREFIX}/health", tags=["health"])
    def health():
        return {
            "status": "ok",
            "app": settings.app_name,
            "env": settings.env,
            "version": "0.1.0",
        }

    @app.get("/", include_in_schema=False)
    def root():
        return {"name": settings.app_name, "docs": "/docs", "health": f"{API_PREFIX}/health"}

    return app


app = create_app()
