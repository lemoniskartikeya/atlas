"""Background job run history.

The scheduler persists every run so "when did this last happen, and did it
work?" survives a restart — and so the next due time can be computed from real
history rather than from an in-memory timer that resets whenever the app is
relaunched (which, for a desktop app, is constantly).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class JobRun(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "job_runs"

    job_id: Mapped[str] = mapped_column(String(40), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    #: "ok" | "skipped" | "error" — "skipped" is a *successful* decision not to
    #: act (e.g. too little new data to justify retraining), and still counts
    #: as the job having run.
    status: Mapped[str] = mapped_column(String(16), index=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, default=None)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, default=None)
