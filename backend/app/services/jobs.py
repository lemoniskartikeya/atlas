"""Background jobs: what Atlas does for itself while you're not looking.

The scheduler is a plain asyncio loop inside the API process — no APScheduler,
no system cron. A desktop app has no daemon to hang jobs off, and its process
is started and stopped constantly, so "next due" is computed from persisted run
history (``job_runs``) rather than an in-memory timer that would reset on every
launch. Miss a week because the app was closed? The job runs shortly after the
next launch instead of never.

Jobs are expected to be *idempotent* and to decide for themselves whether there
is anything worth doing; returning "skipped" is a successful outcome.
"""
from __future__ import annotations

import asyncio
import json
import traceback
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.job import JobRun

log = get_logger("atlas.jobs")

# How often the loop wakes up to see if anything is due. Jobs run on the order
# of days, so this only bounds how late a job can be.
TICK_SECONDS = 15 * 60

# Retraining is pointless without meaningfully more evidence than last time.
RETRAIN_MIN_NEW_ROWS = 25


@dataclass
class JobResult:
    status: str  # "ok" | "skipped" | "error"
    detail: str


@dataclass
class Job:
    id: str
    label: str
    description: str
    interval: timedelta
    run: Callable[[Session], JobResult]


# --------------------------------------------------------------------- jobs
def retrain_model(session: Session) -> JobResult:
    """Retrain the completion model when enough new history has accumulated.

    This is the job that turns "Atlas can get better" into "Atlas does get
    better" — without it the model is frozen at whatever was last trained by
    hand.
    """
    try:
        from app.learning import registry
    except Exception:
        return JobResult("skipped", "ML dependencies are not installed.")

    from app.models.habit import HabitLog

    rows = session.scalar(select(func.count()).select_from(HabitLog)) or 0

    meta = registry.latest_meta()
    if meta:
        trained_on = int((meta.get("metrics") or {}).get("n_rows") or 0)
        new_rows = rows - trained_on
        if new_rows < RETRAIN_MIN_NEW_ROWS:
            return JobResult(
                "skipped",
                f"Only {new_rows} new logged days since the last model "
                f"(need {RETRAIN_MIN_NEW_ROWS}).",
            )

    try:
        from app.services.ml_service import MLService

        result = MLService(session).train()
    except Exception as exc:
        return JobResult("error", f"{type(exc).__name__}: {exc}")

    if not result.get("trained"):
        return JobResult("skipped", str(result.get("reason", "Not enough data yet.")))

    metrics = result.get("metrics") or {}
    auc = metrics.get("roc_auc")
    quality = f", ROC-AUC {auc:.3f}" if isinstance(auc, (int, float)) else ""
    return JobResult(
        "ok",
        f"Trained v{result['version']} on {result.get('n_samples', '?')} examples{quality}.",
    )


def auto_backup(session: Session) -> JobResult:
    """Write a dated JSON snapshot and prune old ones.

    Plaintext: encrypted backups are encrypted in the browser with a passphrase
    the backend never sees, so an unattended job cannot produce one. These live
    in the app's own data directory, alongside the database they protect.
    """
    from pathlib import Path

    from app.services.backup_service import BackupService

    settings = get_settings()
    folder = Path(settings.data_dir) / "backups"
    folder.mkdir(parents=True, exist_ok=True)

    doc = BackupService(session).export()
    payload = doc.model_dump(mode="json") if hasattr(doc, "model_dump") else doc
    name = f"atlas-auto-{date.today().isoformat()}.json"
    (folder / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    keep = 14
    snapshots = sorted(folder.glob("atlas-auto-*.json"))
    for stale in snapshots[:-keep]:
        stale.unlink(missing_ok=True)

    total = sum(
        len(v) for v in (payload.get("data") or {}).values() if isinstance(v, list)
    )
    return JobResult("ok", f"Saved {name} ({total} records). Keeping {keep} snapshots.")


JOBS: list[Job] = [
    Job(
        id="retrain_model",
        label="Retrain completion model",
        description=(
            "Refits the habit-completion model on your latest history so "
            "predictions keep pace with how you actually behave."
        ),
        interval=timedelta(days=7),
        run=retrain_model,
    ),
    Job(
        id="auto_backup",
        label="Automatic backup",
        description="Writes a dated snapshot of everything to your data folder.",
        interval=timedelta(days=1),
        run=auto_backup,
    ),
]

JOBS_BY_ID = {j.id: j for j in JOBS}


# ------------------------------------------------------------------ runner
def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


class JobRunner:
    def __init__(self, session: Session) -> None:
        self.session = session

    def last_run(self, job_id: str) -> Optional[JobRun]:
        return self.session.scalars(
            select(JobRun)
            .where(JobRun.job_id == job_id, JobRun.status != "error")
            .order_by(JobRun.started_at.desc())
            .limit(1)
        ).first()

    def history(self, limit: int = 20) -> list[JobRun]:
        return list(
            self.session.scalars(
                select(JobRun).order_by(JobRun.started_at.desc()).limit(limit)
            )
        )

    def due(self, job: Job, now: datetime) -> bool:
        last = self.last_run(job.id)
        if last is None:
            return True
        started = _aware(last.started_at)
        return started is None or now - started >= job.interval

    def next_due(self, job: Job) -> Optional[datetime]:
        last = self.last_run(job.id)
        started = _aware(last.started_at) if last else None
        return (started + job.interval) if started else None

    def run(self, job: Job, force: bool = False) -> JobRun:
        now = datetime.now(timezone.utc)
        if not force and not self.due(job, now):
            # Recorded so a manual "run" that wasn't due is still visible.
            return self._record(job, now, JobResult("skipped", "Not due yet."), 0)

        started = datetime.now(timezone.utc)
        try:
            result = job.run(self.session)
        except Exception as exc:  # a broken job must not kill the loop
            log.warning("job.failed", extra={"job": job.id, "error": str(exc)})
            traceback.print_exc()
            result = JobResult("error", f"{type(exc).__name__}: {exc}")
        elapsed = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        return self._record(job, started, result, elapsed)

    def _record(
        self, job: Job, started: datetime, result: JobResult, elapsed_ms: int
    ) -> JobRun:
        row = JobRun(
            job_id=job.id,
            started_at=started,
            finished_at=datetime.now(timezone.utc),
            status=result.status,
            detail=result.detail,
            duration_ms=elapsed_ms,
        )
        self.session.add(row)
        self.session.commit()
        log.info(
            "job.ran",
            extra={"job": job.id, "status": result.status, "detail": result.detail},
        )
        return row

    def run_due(self) -> list[JobRun]:
        now = datetime.now(timezone.utc)
        return [self.run(job) for job in JOBS if self.due(job, now)]


async def scheduler_loop(session_factory) -> None:
    """Tick forever, running whatever is due. Cancelled on app shutdown."""
    # A short delay keeps startup snappy and avoids competing with the first
    # page load for the database.
    await asyncio.sleep(20)
    while True:
        try:
            session = session_factory()
            try:
                ran = JobRunner(session).run_due()
                if ran:
                    log.info("jobs.tick", extra={"ran": [r.job_id for r in ran]})
            finally:
                session.close()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # never let the loop die
            log.warning("jobs.tick_failed", extra={"error": str(exc)})
        await asyncio.sleep(TICK_SECONDS)
