"""Background jobs: what Atlas does for itself while you're not looking.

The scheduler is a plain asyncio loop inside the API process — no APScheduler,
no system cron. A desktop app has no daemon to hang jobs off, and its process
is started and stopped constantly, so "next due" is computed from persisted run
history (``job_runs``) rather than an in-memory timer that would reset on every
launch. Miss a week because the app was closed? The job runs shortly after the
next launch instead of never.

Jobs are expected to be *idempotent* and to decide for themselves whether there
is anything worth doing; returning "skipped" is a successful outcome.

Everything here runs **per account**. Each account has its own model, its own
snapshots, and its own ``job_runs`` history — so a schedule is never shared, and
one account being idle can't push out another's retrain. The scheduler walks
every account on each tick via ``acting_as``.
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
from app.core.scoping import acting_as, current_user_id
from app.models.job import JobRun

log = get_logger("atlas.jobs")

# How often the loop wakes up to see if anything is due. Jobs run on the order
# of days, so this only bounds how late a job can be.
TICK_SECONDS = 15 * 60

# Retraining is pointless without meaningfully more evidence than last time.
RETRAIN_MIN_NEW_ROWS = 25

# How often to look again while an account still has *no* model at all.
#
# The weekly cadence below is right for keeping a trained model fresh, but it is
# badly wrong for a new account: the very first attempt runs minutes after
# signing up, finds too little history, records a skip — and then waits a full
# week before looking again. Someone who logs diligently for their first
# fortnight would still have none of the smart features switched on, with no
# way to know why. So until a first model exists, check a few times a day.
FIRST_MODEL_CHECK_INTERVAL = timedelta(hours=3)


def _model_exists(session: Session) -> bool:
    """Whether this account already has a trained model. Never raises."""
    try:
        from app.learning import registry

        return registry.latest_meta(current_user_id(session)) is not None
    except Exception:
        return False


def _retrain_interval(session: Session) -> timedelta:
    """Eager until this account has a model, weekly once it does."""
    return timedelta(days=7) if _model_exists(session) else FIRST_MODEL_CHECK_INTERVAL


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
    #: Optional per-account cadence, consulted instead of ``interval``. Lets a
    #: job lean in while something is still pending and settle down afterwards.
    interval_fn: Optional[Callable[[Session], timedelta]] = None


# --------------------------------------------------------------------- jobs
def _train_model(session: Session) -> dict:
    """Run a training pass. Split out so tests can drive the job's own logic."""
    from app.services.ml_service import MLService

    return MLService(session).train()


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

    user_id = current_user_id(session)
    rows = (
        session.scalar(
            select(func.count())
            .select_from(HabitLog)
            .where(HabitLog.user_id == user_id)
        )
        or 0
    )

    meta = registry.latest_meta(user_id)
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
        result = _train_model(session)
    except Exception as exc:
        return JobResult("error", f"{type(exc).__name__}: {exc}")

    if not result.get("trained"):
        # Say it in the user's terms. Nobody signing up for a habit tracker
        # should have to parse "settled examples across both outcomes" to find
        # out that the answer is simply "keep logging for a while longer".
        have = result.get("n_samples")
        if isinstance(have, int):
            from app.services.ml_service import MIN_SAMPLES

            return JobResult(
                "skipped",
                f"Still gathering evidence — {have} of about {MIN_SAMPLES} habit "
                "days recorded. Atlas keeps checking on its own; there is "
                "nothing for you to do.",
            )
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
    # One folder per account: a shared folder would have each account's daily
    # snapshot overwrite the last one to run, silently leaving only one of them.
    folder = Path(settings.data_dir) / "backups" / current_user_id(session)
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
        interval_fn=_retrain_interval,
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

    @property
    def user_id(self) -> str:
        return current_user_id(self.session)

    def last_run(self, job_id: str) -> Optional[JobRun]:
        return self.session.scalars(
            select(JobRun)
            .where(
                JobRun.user_id == self.user_id,
                JobRun.job_id == job_id,
                JobRun.status != "error",
            )
            .order_by(JobRun.started_at.desc())
            .limit(1)
        ).first()

    def history(self, limit: int = 20) -> list[JobRun]:
        return list(
            self.session.scalars(
                select(JobRun)
                .where(JobRun.user_id == self.user_id)
                .order_by(JobRun.started_at.desc())
                .limit(limit)
            )
        )

    def interval_for(self, job: Job) -> timedelta:
        """The cadence to use for this account right now."""
        if job.interval_fn is None:
            return job.interval
        try:
            return job.interval_fn(self.session)
        except Exception:  # a cadence hint must never stop a job running
            return job.interval

    def due(self, job: Job, now: datetime) -> bool:
        last = self.last_run(job.id)
        if last is None:
            return True
        started = _aware(last.started_at)
        return started is None or now - started >= self.interval_for(job)

    def next_due(self, job: Job) -> Optional[datetime]:
        last = self.last_run(job.id)
        started = _aware(last.started_at) if last else None
        return (started + self.interval_for(job)) if started else None

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


def run_due_for_all(session: Session) -> dict[str, list[JobRun]]:
    """Run whatever is due, for every account in turn.

    The scheduler is the one place with no signed-in user to inherit an
    identity from, so it supplies one explicitly per account. A failure for one
    account is logged and skipped rather than abandoning the rest of the tick.
    """
    from app.services.auth_service import AuthService

    out: dict[str, list[JobRun]] = {}
    for user in AuthService(session).all_users():
        try:
            with acting_as(session, user.id):
                ran = JobRunner(session).run_due()
        except Exception as exc:  # one account's problem is not the others'
            log.warning(
                "jobs.account_failed",
                extra={"account": user.username, "error": str(exc)},
            )
            session.rollback()
            continue
        if ran:
            out[user.username] = ran
    return out


async def scheduler_loop(session_factory) -> None:
    """Tick forever, running whatever is due. Cancelled on app shutdown."""
    # A short delay keeps startup snappy and avoids competing with the first
    # page load for the database.
    await asyncio.sleep(20)
    while True:
        try:
            session = session_factory()
            try:
                ran = run_due_for_all(session)
                if ran:
                    log.info(
                        "jobs.tick",
                        extra={
                            "ran": {
                                who: [r.job_id for r in runs] for who, runs in ran.items()
                            }
                        },
                    )
            finally:
                session.close()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # never let the loop die
            log.warning("jobs.tick_failed", extra={"error": str(exc)})
        await asyncio.sleep(TICK_SECONDS)
