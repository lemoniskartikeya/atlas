"""Analytics service: contribution heatmap (Phase 3 expands this)."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.domain.enums import SUCCESS_STATUSES
from app.repositories.habit_repo import HabitLogRepository
from app.schemas.analytics import HeatmapCell, HeatmapResponse


def _level(count: int, max_count: int) -> int:
    if count <= 0 or max_count <= 0:
        return 0
    ratio = count / max_count
    if ratio <= 0.25:
        return 1
    if ratio <= 0.5:
        return 2
    if ratio <= 0.75:
        return 3
    return 4


class AnalyticsService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.logs = HabitLogRepository(session)

    def heatmap(self, days: int = 365, today: Optional[date] = None) -> HeatmapResponse:
        today = today or date.today()
        start = today - timedelta(days=days - 1)
        counts: dict[date, int] = {}
        for log in self.logs.in_range(start, today):
            if log.status in SUCCESS_STATUSES:
                counts[log.date] = counts.get(log.date, 0) + 1

        max_count = max(counts.values()) if counts else 0
        cells: list[HeatmapCell] = []
        total = 0
        d = start
        while d <= today:
            c = counts.get(d, 0)
            total += c
            cells.append(HeatmapCell(date=d, count=c, level=_level(c, max_count)))
            d += timedelta(days=1)
        return HeatmapResponse(
            start=start, end=today, total=total, max_count=max_count, cells=cells
        )
