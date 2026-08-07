"""Background jobs: scheduling from persisted history, and the retrain gate."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.job import JobRun
from app.services.jobs import (
    JOBS,
    JOBS_BY_ID,
    RETRAIN_MIN_NEW_ROWS,
    JobResult,
    JobRunner,
    retrain_model,
)

BASE = "/api/v1"


def _record(db_session, job_id: str, *, days_ago: float, status: str = "ok"):
    started = datetime.now(timezone.utc) - timedelta(days=days_ago)
    db_session.add(
        JobRun(job_id=job_id, started_at=started, finished_at=started, status=status)
    )
    db_session.commit()


# ----------------------------------------------------------------- scheduling
def test_a_job_that_never_ran_is_due(db_session):
    runner = JobRunner(db_session)
    now = datetime.now(timezone.utc)
    assert all(runner.due(job, now) for job in JOBS)


def test_recent_run_makes_a_job_not_due(db_session):
    job = JOBS_BY_ID["auto_backup"]
    _record(db_session, job.id, days_ago=0.1)
    assert JobRunner(db_session).due(job, datetime.now(timezone.utc)) is False


def test_job_becomes_due_again_after_its_interval(db_session):
    job = JOBS_BY_ID["auto_backup"]
    _record(db_session, job.id, days_ago=job.interval.days + 1)
    assert JobRunner(db_session).due(job, datetime.now(timezone.utc)) is True


def test_due_is_computed_from_persisted_history(db_session):
    """A desktop app restarts constantly; an in-memory timer would forget."""
    job = JOBS_BY_ID["retrain_model"]
    _record(db_session, job.id, days_ago=1)
    # A brand-new runner (i.e. a fresh process) still sees the earlier run.
    assert JobRunner(db_session).due(job, datetime.now(timezone.utc)) is False


def test_errors_do_not_count_as_having_run(db_session):
    """A failed run must not push the schedule out and hide the failure."""
    job = JOBS_BY_ID["auto_backup"]
    _record(db_session, job.id, days_ago=0.1, status="error")
    assert JobRunner(db_session).due(job, datetime.now(timezone.utc)) is True


def test_skipped_counts_as_run(db_session):
    """"Nothing to do" is a successful outcome, not a retry-immediately."""
    job = JOBS_BY_ID["auto_backup"]
    _record(db_session, job.id, days_ago=0.1, status="skipped")
    assert JobRunner(db_session).due(job, datetime.now(timezone.utc)) is False


def test_next_due_follows_the_interval(db_session):
    job = JOBS_BY_ID["auto_backup"]
    _record(db_session, job.id, days_ago=0)
    nxt = JobRunner(db_session).next_due(job)
    assert nxt is not None
    assert nxt > datetime.now(timezone.utc)


# --------------------------------------------------------------------- runner
def test_a_broken_job_is_recorded_not_raised(db_session):
    from app.services.jobs import Job

    def explode(_session):
        raise RuntimeError("boom")

    job = Job(
        id="explodes", label="x", description="x", interval=timedelta(days=1), run=explode
    )
    row = JobRunner(db_session).run(job, force=True)
    assert row.status == "error" and "boom" in row.detail


def test_run_records_duration_and_detail(db_session):
    from app.services.jobs import Job

    job = Job(
        id="noop",
        label="x",
        description="x",
        interval=timedelta(days=1),
        run=lambda _s: JobResult("ok", "did a thing"),
    )
    row = JobRunner(db_session).run(job, force=True)
    assert row.status == "ok" and row.detail == "did a thing"
    assert row.duration_ms is not None and row.finished_at is not None


# --------------------------------------------------------------- retrain gate
def test_retrain_skips_without_enough_new_data(db_session, monkeypatch):
    """Refitting on a handful of extra rows is churn, not learning."""
    import pytest

    registry = pytest.importorskip(
        "app.learning.registry", reason="ML extras not installed"
    )
    # Pretend the last model was trained on far more rows than exist now, so
    # the "enough new evidence?" gate is the thing under test.
    monkeypatch.setattr(
        registry, "latest_meta", lambda: {"version": "v1", "metrics": {"n_rows": 10_000}}
    )

    result = retrain_model(db_session)
    assert result.status == "skipped"
    assert "new logged days" in result.detail


def test_retrain_proceeds_once_enough_new_data_exists(client, db_session, monkeypatch):
    import pytest

    registry = pytest.importorskip(
        "app.learning.registry", reason="ML extras not installed"
    )
    monkeypatch.setattr(
        registry, "latest_meta", lambda: {"version": "v1", "metrics": {"n_rows": 0}}
    )

    # Enough fresh history to clear the gate.
    from datetime import date

    hid = client.post(f"{BASE}/habits", json={"title": "Meditate"}).json()["id"]
    for i in range(RETRAIN_MIN_NEW_ROWS + 5):
        day = date.today() - timedelta(days=i + 1)
        client.post(
            f"{BASE}/habits/{hid}/logs",
            json={"status": "completed", "date": day.isoformat()},
        )

    # Gate passes, so it reaches the trainer — which may still decline on its
    # own terms (too few *settled* examples). Either way the skip is no longer
    # the new-data gate.
    result = retrain_model(db_session)
    assert "new logged days" not in (result.detail or "")


def test_retrain_skips_cleanly_without_ml_installed(db_session, monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "app.learning" or name.startswith("app.learning."):
            raise ImportError("no ML stack")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    result = retrain_model(db_session)
    assert result.status == "skipped"
    assert "not installed" in result.detail


# ------------------------------------------------------------------- endpoints
def test_jobs_endpoint_lists_schedule(client):
    body = client.get(f"{BASE}/jobs").json()
    ids = {j["id"] for j in body["jobs"]}
    assert {"retrain_model", "auto_backup"} <= ids
    assert all("interval_hours" in j for j in body["jobs"])


def test_manual_run_is_recorded(client):
    row = client.post(f"{BASE}/jobs/auto_backup/run").json()
    assert row["job_id"] == "auto_backup"
    assert row["status"] in ("ok", "skipped", "error")

    recent = client.get(f"{BASE}/jobs").json()["recent"]
    assert any(r["job_id"] == "auto_backup" for r in recent)


def test_unknown_job_404s(client):
    assert client.post(f"{BASE}/jobs/nope/run").status_code == 404
