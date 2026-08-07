"""Dashboard aggregation service.

Assembles the home screen payload and generates the Phase-1 recommendation set.
Recommendations here are transparent rule-based heuristics — each ships with a
``reason`` and a ``confidence``. Phase 4/5 swaps the generator for learned models
without changing that contract.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.domain.enums import SUCCESS_STATUSES, TimeOfDay
from app.models.habit import Habit
from app.schemas.dashboard import DashboardResponse, HabitTodayItem, StreakItem
from app.schemas.journal import JournalRead
from app.schemas.task import TaskRead
from app.services import ml_gateway, streaks
from app.services.habit_service import HabitService
from app.services.journal_service import JournalService
from app.services.feedback_service import FeedbackService
from app.services.recommender import Recommender
from app.services.task_service import TaskService

_TOD_ORDER = {
    TimeOfDay.MORNING: 0,
    TimeOfDay.AFTERNOON: 1,
    TimeOfDay.EVENING: 2,
    TimeOfDay.NIGHT: 3,
    TimeOfDay.ANY: 4,
}


def _greeting(now_hour: int) -> str:
    if now_hour < 12:
        return "Good morning"
    if now_hour < 18:
        return "Good afternoon"
    return "Good evening"


class DashboardService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.habit_service = HabitService(session)
        self.task_service = TaskService(session)
        self.journal_service = JournalService(session)

    def build(
        self, today: Optional[date] = None, now_hour: Optional[int] = None
    ) -> DashboardResponse:
        today = today or date.today()
        now_hour = now_hour if now_hour is not None else datetime.now().hour

        habits = list(self.habit_service.list_habits(include_archived=False))

        habits_today: list[HabitTodayItem] = []
        streak_items: list[StreakItem] = []
        completed = 0
        weekly_num = weekly_den = 0.0

        for habit in habits:
            success_dates = {l.date for l in habit.logs if l.status in SUCCESS_STATUSES}
            stats = self.habit_service.compute_stats(habit, today)
            streak_items.append(
                StreakItem(
                    habit_id=habit.id,
                    title=habit.title,
                    current_streak=stats.current_streak,
                    longest_streak=stats.longest_streak,
                )
            )

            num, den = self._weekly_fraction(habit, success_dates, today)
            weekly_num += num
            weekly_den += den

            if self.habit_service.is_due_today(habit, today, success_dates):
                today_log = self.habit_service.today_log(habit, today)
                done = bool(today_log and today_log.status in SUCCESS_STATUSES)
                if done:
                    completed += 1
                habits_today.append(
                    HabitTodayItem(
                        id=habit.id,
                        title=habit.title,
                        category=habit.category,
                        color=habit.color,
                        time_preference=habit.time_preference,
                        priority=habit.priority,
                        estimated_duration_min=habit.estimated_duration_min,
                        current_streak=stats.current_streak,
                        status_today=today_log.status if today_log else None,
                        done_today=done,
                    )
                )

        habits_total = len(habits_today)
        weekly_consistency = (weekly_num / weekly_den) if weekly_den else 0.0
        # Not-done first, then by time-of-day preference.
        habits_today.sort(key=lambda i: (i.done_today, _TOD_ORDER.get(i.time_preference, 4)))
        top_streaks = sorted(
            (s for s in streak_items if s.current_streak > 0),
            key=lambda s: s.current_streak,
            reverse=True,
        )[:5]

        tasks_today = [TaskRead.model_validate(t) for t in self.task_service.list_tasks("today", today)]
        tasks_open = len(self.task_service.tasks.open_tasks())
        suggested = self.task_service.suggested_next(today)
        suggested_task = TaskRead.model_validate(suggested) if suggested else None

        latest_journal = self.journal_service.latest()
        recent_journal = JournalRead.model_validate(latest_journal) if latest_journal else None
        mood = latest_journal.mood if latest_journal else None
        energy = latest_journal.energy if latest_journal else None
        sleep_hours = latest_journal.sleep_hours if latest_journal else None

        life_score, focus_score = self._scores(
            weekly_consistency, completed, habits_total, mood, energy
        )
        life_trend = self._life_trend(habits, today)

        predictions, reliability = ml_gateway.habit_predictions(self.session, today)

        # The feedback loop rides on the dashboard rather than a background job
        # so it keeps working whether or not the scheduler is enabled. Both
        # calls are cheap and idempotent: resolution only touches finished days,
        # and recording skips anything already logged for today.
        feedback = FeedbackService(self.session)
        feedback.resolve_due(today)

        recommendations = Recommender(
            predictions=predictions,
            reliability=reliability,
            weights=feedback.weights(today),
        ).build(
            habits_today=habits_today,
            weekly_consistency=weekly_consistency,
            journal=latest_journal,
            suggested=suggested_task,
            now_hour=now_hour,
        )
        # Recorded after ranking, so what's stored is what was actually shown.
        feedback.record_shown(recommendations, today)

        return DashboardResponse(
            date=today,
            greeting=_greeting(now_hour),
            habits_today=habits_today,
            habits_completed=completed,
            habits_total=habits_total,
            tasks_today=tasks_today,
            tasks_open=tasks_open,
            suggested_task=suggested_task,
            top_streaks=top_streaks,
            weekly_consistency=round(weekly_consistency, 4),
            life_score=life_score,
            life_score_trend=life_trend,
            focus_score=focus_score,
            mood=mood,
            energy=energy,
            sleep_hours=sleep_hours,
            recent_journal=recent_journal,
            recommendations=recommendations,
            recommendations_model_backed=predictions is not None,
        )

    # ----------------------------------------------------------------- scoring
    @staticmethod
    def _weekly_fraction(
        habit: Habit, success_dates: set[date], today: date
    ) -> tuple[float, float]:
        """Successful vs. due occurrence-days over the trailing 7 days."""
        num = den = 0.0
        for i in range(7):
            d = today - timedelta(days=i)
            if streaks.is_occurrence_day(habit.frequency, habit.custom_days, d):
                den += 1
                if d in success_dates:
                    num += 1
        return num, den

    @staticmethod
    def _scores(
        weekly_consistency: float,
        completed: int,
        habits_total: int,
        mood: Optional[int],
        energy: Optional[int],
    ) -> tuple[float, float]:
        """Transparent composite scores (documented in the README).

        life  = 40% weekly consistency + 25% today's completion
                + 17.5% mood + 17.5% energy
        focus = 60% today's completion + 40% energy
        """
        habit_c = weekly_consistency
        today_c = (completed / habits_total) if habits_total else weekly_consistency
        mood_c = ((mood - 1) / 4) if mood else 0.6
        energy_c = ((energy - 1) / 4) if energy else 0.6
        life = 100 * (0.40 * habit_c + 0.25 * today_c + 0.175 * mood_c + 0.175 * energy_c)
        focus = 100 * (0.60 * today_c + 0.40 * energy_c)
        return round(life, 1), round(focus, 1)

    def _life_trend(self, habits: list[Habit], today: date, days: int = 14) -> list[float]:
        trend: list[float] = []
        for i in range(days - 1, -1, -1):
            d = today - timedelta(days=i)
            num = den = 0
            for habit in habits:
                if not streaks.is_occurrence_day(habit.frequency, habit.custom_days, d):
                    continue
                den += 1
                if any(l.date == d and l.status in SUCCESS_STATUSES for l in habit.logs):
                    num += 1
            trend.append(round(100 * num / den, 1) if den else 0.0)
        return trend
