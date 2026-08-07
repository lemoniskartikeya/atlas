"""Weekly review: a narrative, explainable recap generated from the user's data.

No external model or service — every sentence is derived from counts, rates, and
journal averages the user can verify. Compares the selected ISO week against the
prior week so wins and slips are framed against a baseline.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.domain.enums import SUCCESS_STATUSES
from app.models.habit import Habit
from app.core.timeutil import local_day
from app.schemas.review import ReviewItem, ReviewMetric, WeeklyReview
from app.services import streaks
from app.services.habit_service import HabitService
from app.services.journal_service import JournalService
from app.services.task_service import TaskService

_MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def _fmt_range(start: date, end: date) -> str:
    if start.month == end.month:
        return f"{_MONTHS[start.month - 1]} {start.day}–{end.day}"
    return f"{_MONTHS[start.month - 1]} {start.day} – {_MONTHS[end.month - 1]} {end.day}"


def _direction(delta: Optional[float]) -> Optional[str]:
    if delta is None:
        return None
    if delta > 0.005:
        return "up"
    if delta < -0.005:
        return "down"
    return "flat"


def _avg(values: list) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return (sum(vals) / len(vals)) if vals else None


class WeeklyReviewService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.habits = HabitService(session)
        self.tasks = TaskService(session)
        self.journals = JournalService(session)

    @staticmethod
    def _window(today: date, offset: int) -> tuple[date, date]:
        monday = today - timedelta(days=today.weekday())
        start = monday - timedelta(weeks=offset)
        end = min(start + timedelta(days=6), today)
        return start, end

    def build(self, offset: int = 0, today: Optional[date] = None) -> WeeklyReview:
        today = today or date.today()
        offset = max(0, offset)
        start, end = self._window(today, offset)
        p_start, p_end = self._window(today, offset + 1)

        habits = list(self.habits.list_habits(include_archived=False))
        rate, done, due, rows = self._per_habit(habits, start, end)
        p_rate, _, p_due, p_rows = self._per_habit(habits, p_start, p_end)
        prev_by_id = {h.id: r for (h, _d, _n, r) in p_rows}
        prev_rate = p_rate if p_due else None

        mood, energy, sleep = self._wellbeing(start, end)
        p_mood, p_energy, p_sleep = self._wellbeing(p_start, p_end)
        tasks_completed = self._tasks_completed(start, end)

        metrics = [
            self._metric("completion", "Completion", f"{round(rate * 100)}%", rate, prev_rate),
            self._metric("mood", "Avg mood", self._num(mood, "/5"), mood, p_mood),
            self._metric("energy", "Avg energy", self._num(energy, "/5"), energy, p_energy),
            self._metric("sleep", "Avg sleep", self._num(sleep, "h"), sleep, p_sleep),
            ReviewMetric(key="tasks", label="Tasks done", value=str(tasks_completed)),
        ]

        wins = self._wins(rows, prev_by_id)
        watchouts = self._watchouts(rows, prev_by_id)
        focus = self._focus(watchouts, sleep)
        narrative = self._narrative(rate, prev_rate, done, due, wins, watchouts, mood, energy, sleep)

        label = "This week" if offset == 0 else "Last week" if offset == 1 else _fmt_range(start, end)

        return WeeklyReview(
            start=start,
            end=end,
            label=label,
            offset=offset,
            is_current=offset == 0,
            can_go_forward=offset > 0,
            completion_rate=round(rate, 4),
            prev_completion_rate=round(prev_rate, 4) if prev_rate is not None else None,
            completions=done,
            due=due,
            tasks_completed=tasks_completed,
            metrics=metrics,
            wins=wins,
            watchouts=watchouts,
            focus=focus,
            narrative=narrative,
        )

    # ----------------------------------------------------------------- helpers
    @staticmethod
    def _num(v: Optional[float], suffix: str) -> str:
        return f"{v:.1f}{suffix}" if v is not None else "—"

    @staticmethod
    def _metric(
        key: str, label: str, value: str, cur: Optional[float], prev: Optional[float]
    ) -> ReviewMetric:
        delta = round(cur - prev, 3) if (cur is not None and prev is not None) else None
        return ReviewMetric(
            key=key, label=label, value=value, delta=delta, direction=_direction(delta)
        )

    def _per_habit(self, habits: list[Habit], start: date, end: date):
        """Return (overall_rate, done, due, [(habit, due, done, rate)])."""
        rows = []
        tot_due = tot_done = 0
        for habit in habits:
            success = {l.date for l in habit.logs if l.status in SUCCESS_STATUSES}
            h_due = h_done = 0
            d = start
            while d <= end:
                if streaks.is_occurrence_day(habit.frequency, habit.custom_days, d):
                    h_due += 1
                    if d in success:
                        h_done += 1
                d += timedelta(days=1)
            tot_due += h_due
            tot_done += h_done
            if h_due > 0:
                rows.append((habit, h_due, h_done, h_done / h_due))
        rate = (tot_done / tot_due) if tot_due else 0.0
        return rate, tot_done, tot_due, rows

    def _wellbeing(self, start: date, end: date):
        js = [j for j in self.journals.recent(400) if start <= j.date <= end]
        return (
            _avg([j.mood for j in js]),
            _avg([j.energy for j in js]),
            _avg([j.sleep_hours for j in js]),
        )

    def _tasks_completed(self, start: date, end: date) -> int:
        n = 0
        for t in self.tasks.tasks.list_all():
            # local_day, not .date(): a task finished late in the evening must
            # count toward the week the user actually finished it in.
            day = local_day(t.completed_at)
            if day and start <= day <= end:
                n += 1
        return n

    @staticmethod
    def _wins(rows, prev_by_id) -> list[ReviewItem]:
        items: list[ReviewItem] = []
        strong = sorted(
            [r for r in rows if r[1] >= 2 and r[3] >= 0.8],
            key=lambda r: (-r[3], -(r[3] - prev_by_id.get(r[0].id, 0.0))),
        )
        for habit, h_due, h_done, rate in strong[:3]:
            prev = prev_by_id.get(habit.id)
            head = "Flawless" if rate >= 0.999 else "Strong"
            detail = f"{head} — {h_done}/{h_due} ({round(rate * 100)}%)"
            if prev is not None and rate - prev >= 0.15:
                detail += f", up {round((rate - prev) * 100)} pts"
            items.append(ReviewItem(title=habit.title, detail=detail + ".", habit_id=habit.id))

        have = {i.habit_id for i in items}
        improved = sorted(
            [
                r
                for r in rows
                if r[1] >= 2
                and prev_by_id.get(r[0].id) is not None
                and r[3] - prev_by_id[r[0].id] >= 0.25
                and r[0].id not in have
            ],
            key=lambda r: -(r[3] - prev_by_id[r[0].id]),
        )
        for habit, _due, _done, rate in improved[:1]:
            prev = prev_by_id[habit.id]
            items.append(
                ReviewItem(
                    title=habit.title,
                    detail=f"Most improved — {round(prev * 100)}% → {round(rate * 100)}%.",
                    habit_id=habit.id,
                )
            )
        return items[:3]

    @staticmethod
    def _watchouts(rows, prev_by_id) -> list[ReviewItem]:
        weak = sorted(
            [r for r in rows if r[1] >= 2 and r[3] < 0.6],
            key=lambda r: (r[3], r[3] - prev_by_id.get(r[0].id, r[3])),
        )
        items: list[ReviewItem] = []
        for habit, h_due, h_done, rate in weak[:3]:
            prev = prev_by_id.get(habit.id)
            detail = f"Only {h_done}/{h_due} ({round(rate * 100)}%)"
            if prev is not None and prev - rate >= 0.15:
                detail += f", down from {round(prev * 100)}%"
            items.append(ReviewItem(title=habit.title, detail=detail + ".", habit_id=habit.id))
        return items

    @staticmethod
    def _focus(watchouts: list[ReviewItem], sleep: Optional[float]) -> list[str]:
        focus: list[str] = []
        for w in watchouts[:2]:
            focus.append(f"Give “{w.title}” a fixed slot to rebuild consistency.")
        if sleep is not None and sleep < 6.8:
            focus.append(f"Protect sleep — it averaged {sleep:.1f}h this week.")
        if not focus:
            focus.append("Keep the momentum — you're in a good rhythm.")
        return focus[:3]

    @staticmethod
    def _narrative(
        rate, prev, done, due, wins, watchouts, mood, energy, sleep
    ) -> str:
        if due == 0:
            return "No habits were due this week. Add or schedule a few to start building a picture."

        parts = [f"You completed {round(rate * 100)}% of your due habit-days ({done}/{due})"]
        if prev is not None:
            d = round((rate - prev) * 100)
            if d > 0:
                parts[0] += f", up {d} points from last week."
            elif d < 0:
                parts[0] += f", down {abs(d)} points from last week."
            else:
                parts[0] += ", level with last week."
        else:
            parts[0] += "."

        if wins:
            parts.append(f"{wins[0].title} led the way.")
        if watchouts:
            parts.append(f"{watchouts[0].title} slipped and is worth protecting.")

        bits = []
        if sleep is not None:
            bits.append(f"{sleep:.1f}h sleep")
        if energy is not None:
            bits.append(f"{energy:.1f}/5 energy")
        if mood is not None:
            bits.append(f"mood {mood:.1f}/5")
        if bits:
            parts.append("On wellbeing, you averaged " + ", ".join(bits) + ".")

        return " ".join(parts)
