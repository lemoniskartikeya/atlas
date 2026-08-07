"""Background-job DTOs."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class JobRunOut(BaseModel):
    job_id: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: str  # "ok" | "skipped" | "error"
    detail: Optional[str] = None
    duration_ms: Optional[int] = None


class JobOut(BaseModel):
    id: str
    label: str
    description: str
    interval_hours: float
    last_run: Optional[JobRunOut] = None
    next_due: Optional[datetime] = None
    due_now: bool = False


class JobsResponse(BaseModel):
    enabled: bool
    jobs: list[JobOut]
    recent: list[JobRunOut] = []
