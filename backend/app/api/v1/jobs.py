"""Background-job endpoints: what Atlas runs for itself, and when."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_session
from app.schemas.jobs import JobOut, JobRunOut, JobsResponse
from app.services.jobs import JOBS, JOBS_BY_ID, JobRunner

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _runner(session: Session = Depends(get_session)) -> JobRunner:
    return JobRunner(session)


@router.get("", response_model=JobsResponse)
def list_jobs(runner: JobRunner = Depends(_runner)):
    now = datetime.now(timezone.utc)
    return JobsResponse(
        enabled=get_settings().jobs_enabled,
        jobs=[
            JobOut(
                id=job.id,
                label=job.label,
                description=job.description,
                interval_hours=job.interval.total_seconds() / 3600,
                last_run=(
                    JobRunOut.model_validate(last, from_attributes=True)
                    if (last := runner.last_run(job.id))
                    else None
                ),
                next_due=runner.next_due(job),
                due_now=runner.due(job, now),
            )
            for job in JOBS
        ],
        recent=[
            JobRunOut.model_validate(r, from_attributes=True) for r in runner.history(20)
        ],
    )


@router.post("/{job_id}/run", response_model=JobRunOut)
def run_job(job_id: str, runner: JobRunner = Depends(_runner)):
    """Run a job immediately, regardless of its schedule."""
    job = JOBS_BY_ID.get(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown job")
    row = runner.run(job, force=True)
    return JobRunOut.model_validate(row, from_attributes=True)
