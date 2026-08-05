"""Habit domain service: CRUD, logging, and the stats/streak engine glue."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.domain.enums import (
    Frequency,
    HabitLogStatus,
    SUCCESS_STATUSES,
    WEEKDAY_NAMES,
)
from app.models.habit import Habit, HabitLog
from app.repositories.habit_repo import HabitLogRepository, HabitRepository
from app.schemas.habit import HabitCreate, HabitLogCreate, HabitStats, HabitUpdate
from app.services import streaks


class HabitService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.habits = HabitRepository(session)
        self.logs = HabitLogRepository(session)

    # ------------------------------------------------------------------ CRUD
    def list_habits(self, include_archived: bool = False) -> Sequence[Habit]:
        return self.habits.list_all(include_archived)

    def get_habit(self, habit_id: str) -> Optional[Habit]:
        return self.habits.get(habit_id)

    def create_habit(self, data: HabitCreate) -> Habit:
        habit = Habit(**data.model_dump())
        self.habits.add(habit)
        self.habits.commit()
        return habit

    def update_habit(self, habit: Habit, data: HabitUpdate) -> Habit:
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(habit, key, value)
        self.habits.commit()
        return habit

    def delete_habit(self, habit: Habit) -> None:
        self.habits.delete(habit)
        self.habits.commit()

    # --------------------------------------------------------------- logging
    def log_habit(self, habit: Habit, data: HabitLogCreate) -> HabitLog:
        """Upsert the log for (habit, date). One log per habit per day."""
        d = data.date or date.today()
        payload = data.model_dump(exclude_unset=True)
        payload.pop("date", None)
        existing = self.logs.for_habit_and_date(habit.id, d)
        if existing:
            for key, value in payload.items():
                setattr(existing, key, value)
            log = existing
        else:
            log = HabitLog(habit_id=habit.id, date=d, **payload)
            self.logs.add(log)
        self.logs.commit()
        return log

    def unlog_habit(self, habit: Habit, d: date) -> bool:
        existing = self.logs.for_habit_and_date(habit.id, d)
        if existing is None:
            return False
        self.logs.delete(existing)
        self.logs.commit()
        return True

    def logs_for(self, habit: Habit) -> Sequence[HabitLog]:
        return self.logs.for_habit(habit.id)

    # ----------------------------------------------------------- today helpers
    def today_log(self, habit: Habit, today: date) -> Optional[HabitLog]:
        for log in habit.logs:
            if log.date == today:
                return log
        return None

    def is_due_today(
        self, habit: Habit, today: date, success_dates: Optional[set[date]] = None
    ) -> bool:
        if habit.frequency == Frequency.DAILY:
            return True
        if habit.frequency == Frequency.CUSTOM:
            return today.weekday() in set(habit.custom_days or [])
        # WEEKLY / MONTHLY: due while this period's target isn't met yet.
        if success_dates is None:
            success_dates = {l.date for l in habit.logs if l.status in SUCCESS_STATUSES}
        key = streaks.period_key(habit.frequency, today)
        done = sum(1 for sd in success_dates if streaks.period_key(habit.frequency, sd) == key)
        return done < habit.target_per_period

    # -------------------------------------------------------------- analytics
    def compute_stats(self, habit: Habit, today: Optional[date] = None) -> HabitStats:
        today = today or date.today()
        logs = list(habit.logs)
        success_dates = {l.date for l in logs if l.status in SUCCESS_STATUSES}
        completed_logs = [l for l in logs if l.status == HabitLogStatus.COMPLETED]
        earliest = min((l.date for l in logs), default=today)

        all_periods = streaks.build_periods(
            habit.frequency, habit.custom_days, habit.target_per_period,
            success_dates, earliest, today,
        )
        current, longest = streaks.compute_streaks(all_periods)
        rate = streaks.success_rate(all_periods)

        window_start = max(earliest, today - timedelta(days=29))
        window_periods = streaks.build_periods(
            habit.frequency, habit.custom_days, habit.target_per_period,
            success_dates, window_start, today,
        )
        consistency = streaks.success_rate(window_periods)

        best_wd, worst_wd = self._weekday_extremes(habit, success_dates, earliest, today)

        hour: Optional[int] = None
        if completed_logs:
            hours = Counter(l.logged_at.hour for l in completed_logs if l.logged_at)
            if hours:
                hour = hours.most_common(1)[0][0]

        durations = [l.duration_min for l in logs if l.duration_min]
        avg_dur = (sum(durations) / len(durations)) if durations else None

        return HabitStats(
            habit_id=habit.id,
            current_streak=current,
            longest_streak=longest,
            total_completions=len(completed_logs),
            success_rate=round(rate, 4),
            consistency_30d=round(consistency, 4),
            best_weekday=best_wd,
            worst_weekday=worst_wd,
            most_productive_hour=hour,
            average_duration_min=round(avg_dur, 1) if avg_dur is not None else None,
            last_completed=max(success_dates) if success_dates else None,
        )

    def _weekday_extremes(
        self, habit: Habit, success_dates: set[date], start: date, today: date
    ) -> tuple[Optional[str], Optional[str]]:
        due: dict[int, int] = defaultdict(int)
        done: dict[int, int] = defaultdict(int)
        d = start
        while d <= today:
            if streaks.is_occurrence_day(habit.frequency, habit.custom_days, d):
                due[d.weekday()] += 1
                if d in success_dates:
                    done[d.weekday()] += 1
            d += timedelta(days=1)
        # Need at least a couple of occurrences on a weekday for the rate to mean anything.
        rates = {wd: done[wd] / n for wd, n in due.items() if n >= 2}
        if not rates:
            return None, None
        best = max(rates, key=rates.get)
        worst = min(rates, key=rates.get)
        best_name = WEEKDAY_NAMES[best]
        worst_name = WEEKDAY_NAMES[worst] if worst != best else None
        return best_name, worst_name
