"""Analytics service: heatmap, summary KPIs, weekly productivity, correlations.

The correlation math is pure (module-level ``pearson`` / ``interpret``) so it is
unit-tested directly and reusable by the future ML feature pipeline.
"""
from __future__ import annotations

from collections import OrderedDict, defaultdict
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.domain.enums import SUCCESS_STATUSES, HabitLogStatus, TaskStatus
from app.repositories.habit_repo import HabitLogRepository, HabitRepository
from app.repositories.journal_repo import JournalRepository
from app.repositories.task_repo import TaskRepository
from app.schemas.analytics import (
    AnalyticsSummary,
    CategoryCount,
    CorrelationPair,
    CorrelationPoint,
    CorrelationsResponse,
    HeatmapCell,
    HeatmapResponse,
    TopHabit,
    WeeklyPoint,
    WeeklyResponse,
)
from app.services import streaks
from app.services.habit_service import HabitService


# ------------------------------------------------------------- pure stats

def pearson(xs: list[float], ys: list[float]) -> Optional[float]:
    """Pearson correlation coefficient, or None if undefined / < 3 points."""
    n = len(xs)
    if n < 3 or n != len(ys):
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 0 or vy <= 0:
        return None
    return cov / ((vx * vy) ** 0.5)


def interpret(coeff: Optional[float], n: int, x_label: str, y_label: str) -> str:
    if coeff is None or n < 5:
        return f"Not enough overlapping days yet to relate {x_label.lower()} and {y_label}."
    mag = abs(coeff)
    if mag < 0.1:
        strength = "little to no"
    elif mag < 0.3:
        strength = "a weak"
    elif mag < 0.5:
        strength = "a moderate"
    else:
        strength = "a strong"
    direction = "higher" if coeff > 0 else "lower"
    return (
        f"More {x_label.lower()} shows {strength} association with {direction} {y_label} "
        f"(r={coeff:.2f}, {n} days). Correlation, not causation."
    )


def _avg(values: list[Optional[float]]) -> Optional[float]:
    nums = [v for v in values if v is not None]
    return round(sum(nums) / len(nums), 2) if nums else None


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
        self.habits = HabitRepository(session)
        self.journal = JournalRepository(session)
        self.tasks = TaskRepository(session)
        self.habit_service = HabitService(session)

    # --------------------------------------------------------------- heatmap
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
        return HeatmapResponse(start=start, end=today, total=total, max_count=max_count, cells=cells)

    # ----------------------------------------------------- per-day joined frame
    def _daily_rows(self, days: int, today: date) -> list[dict]:
        """One row per day: habit due/done counts joined with the journal metrics."""
        start = today - timedelta(days=days - 1)
        habits = list(self.habits.list_all(include_archived=False))
        journals = {j.date: j for j in self.journal.in_range(start, today)}
        # Pre-index success dates per habit to avoid re-scanning logs each day.
        success: list[set[date]] = [
            {l.date for l in h.logs if l.status in SUCCESS_STATUSES} for h in habits
        ]

        rows: list[dict] = []
        d = start
        while d <= today:
            due = done = 0
            for habit, succ in zip(habits, success):
                if streaks.is_occurrence_day(habit.frequency, habit.custom_days, d):
                    due += 1
                    if d in succ:
                        done += 1
            j = journals.get(d)
            rows.append(
                {
                    "date": d,
                    "due": due,
                    "done": done,
                    "rate": (done / due) if due else None,
                    "mood": j.mood if j else None,
                    "energy": j.energy if j else None,
                    "sleep": j.sleep_hours if j else None,
                }
            )
            d += timedelta(days=1)
        return rows

    # --------------------------------------------------------------- summary
    def summary(self, today: Optional[date] = None) -> AnalyticsSummary:
        today = today or date.today()
        habits = list(self.habits.list_all(include_archived=False))

        by_weekday = [0] * 7
        by_category: dict[str, int] = defaultdict(int)
        total_completed = 0
        deep_work_min = 0
        best_current = 0
        longest_ever = 0
        top: list[TopHabit] = []

        for habit in habits:
            stats = self.habit_service.compute_stats(habit, today)
            best_current = max(best_current, stats.current_streak)
            longest_ever = max(longest_ever, stats.longest_streak)
            top.append(
                TopHabit(
                    id=habit.id,
                    title=habit.title,
                    current_streak=stats.current_streak,
                    longest_streak=stats.longest_streak,
                    success_rate=stats.success_rate,
                    consistency_30d=stats.consistency_30d,
                    total_completions=stats.total_completions,
                )
            )
            for log in habit.logs:
                if log.status in SUCCESS_STATUSES:
                    by_weekday[log.date.weekday()] += 1
                    by_category[habit.category or "Uncategorized"] += 1
                if log.status == HabitLogStatus.COMPLETED:
                    total_completed += 1
                if log.duration_min:
                    deep_work_min += log.duration_min

        top.sort(key=lambda t: (t.total_completions, t.current_streak), reverse=True)

        journals = list(self.journal.recent(400))
        all_tasks = list(self.tasks.list_all())
        tasks_completed = sum(1 for t in all_tasks if t.status == TaskStatus.DONE)
        tasks_open = len(list(self.tasks.open_tasks()))

        categories = sorted(
            (CategoryCount(category=c, count=n) for c, n in by_category.items()),
            key=lambda c: c.count,
            reverse=True,
        )

        return AnalyticsSummary(
            total_completions=total_completed,
            active_habits=len(habits),
            journal_entries=len(journals),
            tasks_completed=tasks_completed,
            tasks_open=tasks_open,
            best_current_streak=best_current,
            longest_streak_ever=longest_ever,
            avg_mood=_avg([j.mood for j in journals]),
            avg_energy=_avg([j.energy for j in journals]),
            avg_sleep=_avg([j.sleep_hours for j in journals]),
            deep_work_hours=round(deep_work_min / 60, 1),
            by_weekday=by_weekday,
            by_category=categories,
            top_habits=top[:8],
        )

    # --------------------------------------------------------------- weekly
    def weekly(self, weeks: int = 12, today: Optional[date] = None) -> WeeklyResponse:
        today = today or date.today()
        rows = self._daily_rows(weeks * 7, today)
        buckets: "OrderedDict[tuple, dict]" = OrderedDict()
        for r in rows:
            iso = r["date"].isocalendar()
            key = (iso.year, iso.week)
            b = buckets.setdefault(key, {"due": 0, "done": 0, "start": r["date"]})
            b["due"] += r["due"]
            b["done"] += r["done"]
            if r["date"] < b["start"]:
                b["start"] = r["date"]

        points = [
            WeeklyPoint(
                week_start=b["start"],
                label=b["start"].strftime("%b %d"),
                completions=b["done"],
                rate=round(b["done"] / b["due"], 3) if b["due"] else 0.0,
            )
            for b in buckets.values()
        ]
        return WeeklyResponse(weeks=points[-weeks:])

    # ---------------------------------------------------------- correlations
    def correlations(self, days: int = 90, today: Optional[date] = None) -> CorrelationsResponse:
        today = today or date.today()
        rows = self._daily_rows(days, today)
        specs = [("sleep", "Sleep"), ("mood", "Mood"), ("energy", "Energy")]

        pairs: list[CorrelationPair] = []
        for key, x_label in specs:
            pts = [
                (float(r[key]), r["rate"] * 100.0, r["date"])
                for r in rows
                if r[key] is not None and r["rate"] is not None
            ]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            coeff = pearson(xs, ys)
            pairs.append(
                CorrelationPair(
                    key=key,
                    x_label=x_label,
                    y_label="completion rate",
                    coefficient=round(coeff, 3) if coeff is not None else None,
                    n=len(pts),
                    interpretation=interpret(coeff, len(pts), x_label, "completion rate"),
                    points=[
                        CorrelationPoint(date=p[2], x=round(p[0], 2), y=round(p[1], 1))
                        for p in pts
                    ],
                )
            )
        return CorrelationsResponse(pairs=pairs)
