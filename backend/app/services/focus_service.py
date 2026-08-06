"""Focus-session service: log deep-work blocks and summarize them."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.models.focus import FocusSession
from app.repositories.focus_repo import FocusRepository
from app.schemas.focus import FocusSessionCreate


def _local_day(dt: datetime) -> date:
    """The calendar day a session belongs to (naive-UTC → date)."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.date()


class FocusService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = FocusRepository(session)

    def create(self, data: FocusSessionCreate) -> FocusSession:
        payload = data.model_dump(exclude_unset=True)
        payload.setdefault("started_at", datetime.now(timezone.utc))
        fs = FocusSession(**payload)
        self.repo.add(fs)
        self.repo.commit()
        return fs

    def recent(self, limit: int = 20) -> Sequence[FocusSession]:
        return self.repo.recent(limit)

    def stats(self, today: Optional[date] = None) -> dict:
        today = today or date.today()
        week_start = today - timedelta(days=6)

        sessions_today = minutes_today = 0
        sessions_week = minutes_week = 0
        distractions_week: list[int] = []
        by_day: dict[date, int] = defaultdict(int)

        for fs in self.repo.list():
            d = _local_day(fs.started_at)
            if d == today:
                sessions_today += 1
                minutes_today += fs.duration_min
            if week_start <= d <= today:
                sessions_week += 1
                minutes_week += fs.duration_min
                distractions_week.append(fs.distractions)
                by_day[d] += fs.duration_min

        avg = round(sum(distractions_week) / len(distractions_week), 1) if distractions_week else None
        best_day = max(by_day.values(), default=0)

        return {
            "sessions_today": sessions_today,
            "minutes_today": minutes_today,
            "sessions_week": sessions_week,
            "minutes_week": minutes_week,
            "avg_distractions": avg,
            "best_day_minutes": best_day,
        }
