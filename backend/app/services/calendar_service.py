"""Calendar: one month of everything, laid out on a grid.

Aggregates habit logs, tasks, journal entries, and focus sessions per day. Pure
local aggregation over existing repositories — no new storage.

A deliberate distinction runs through this file: **the past shows what
happened, the future shows what is scheduled.** Past days are built from real
logs. Future days only project habits whose schedule is genuinely day-specific
(daily, or custom weekdays). Weekly/monthly habits carry a target per period
rather than a day, so pinning them to a square would be inventing a commitment
the user never made.
"""
from __future__ import annotations

import calendar as calmod
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutil import local_day
from app.domain.enums import Frequency, HabitLogStatus, SUCCESS_STATUSES, TaskStatus
from app.models.focus import FocusSession
from app.models.habit import Habit
from app.repositories.habit_repo import HabitLogRepository, HabitRepository
from app.repositories.journal_repo import JournalRepository
from app.repositories.task_repo import TaskRepository
from app.schemas.calendar import CalendarDay, CalendarHabit, CalendarMonth, CalendarTask

_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

_STATUS_NAME = {
    HabitLogStatus.COMPLETED: "completed",
    HabitLogStatus.PARTIAL: "partial",
    HabitLogStatus.SKIPPED: "skipped",
}


class CalendarService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.habits = HabitRepository(session)
        self.logs = HabitLogRepository(session)
        self.tasks = TaskRepository(session)
        self.journals = JournalRepository(session)

    def month(self, year: int, month: int, today: Optional[date] = None) -> CalendarMonth:
        today = today or date.today()

        first = date(year, month, 1)
        last = date(year, month, calmod.monthrange(year, month)[1])
        # Pad out to whole Monday-first weeks so the grid is always 7 wide.
        start = first - timedelta(days=first.weekday())
        end = last + timedelta(days=6 - last.weekday())

        habits = list(self.habits.list_all(include_archived=False))
        by_id = {h.id: h for h in habits}

        # --- logs -----------------------------------------------------------
        logs_by_day: dict[date, list] = {}
        for log in self.logs.in_range(start, end):
            logs_by_day.setdefault(log.date, []).append(log)

        # --- tasks ----------------------------------------------------------
        due_by_day: dict[date, list] = {}
        done_by_day: dict[date, list] = {}
        for task in self.tasks.list_all():
            if task.due_date and start <= task.due_date <= end:
                due_by_day.setdefault(task.due_date, []).append(task)
            if task.status == TaskStatus.DONE and task.completed_at:
                day = local_day(task.completed_at, start)
                if start <= day <= end:
                    done_by_day.setdefault(day, []).append(task)

        # --- journal --------------------------------------------------------
        journal_by_day = {j.date: j for j in self.journals.in_range(start, end)}

        # --- focus ----------------------------------------------------------
        focus_by_day: dict[date, list[FocusSession]] = {}
        for fs in self.session.scalars(select(FocusSession)):
            day = local_day(fs.started_at, start)
            if start <= day <= end:
                focus_by_day.setdefault(day, []).append(fs)

        days: list[CalendarDay] = []
        cursor = start
        while cursor <= end:
            days.append(
                self._build_day(
                    cursor,
                    today=today,
                    in_month=cursor.month == month and cursor.year == year,
                    habits=habits,
                    by_id=by_id,
                    logs=logs_by_day.get(cursor, []),
                    due_tasks=due_by_day.get(cursor, []),
                    done_tasks=done_by_day.get(cursor, []),
                    journal=journal_by_day.get(cursor),
                    focus=focus_by_day.get(cursor, []),
                )
            )
            cursor += timedelta(days=1)

        in_month = [d for d in days if d.in_month]
        return CalendarMonth(
            year=year,
            month=month,
            label=f"{_MONTHS[month - 1]} {year}",
            days=days,
            total_habits_done=sum(d.habits_done for d in in_month),
            total_tasks_completed=sum(d.tasks_completed for d in in_month),
            total_focus_minutes=sum(d.focus_minutes for d in in_month),
            journal_days=sum(1 for d in in_month if d.has_journal),
            # A "perfect day" needs something to have actually been due.
            perfect_days=sum(
                1 for d in in_month if d.habits_due > 0 and d.habits_done == d.habits_due
            ),
        )

    # ------------------------------------------------------------------ internals
    def _build_day(
        self,
        day: date,
        *,
        today: date,
        in_month: bool,
        habits: list[Habit],
        by_id: dict[str, Habit],
        logs: list,
        due_tasks: list,
        done_tasks: list,
        journal,
        focus: list[FocusSession],
    ) -> CalendarDay:
        is_future = day > today

        entries: list[CalendarHabit] = []
        logged_ids: set[str] = set()
        done = 0

        for log in logs:
            habit = by_id.get(log.habit_id)
            if habit is None:  # archived or deleted since
                continue
            logged_ids.add(habit.id)
            if log.status in SUCCESS_STATUSES:
                done += 1
            entries.append(
                CalendarHabit(
                    id=habit.id,
                    title=habit.title,
                    color=habit.color,
                    status=_STATUS_NAME.get(log.status, "completed"),
                )
            )

        # Anything scheduled but not logged: a gap in the past, a plan ahead.
        for habit in habits:
            if habit.id in logged_ids or not self._scheduled_on(habit, day):
                continue
            entries.append(
                CalendarHabit(
                    id=habit.id, title=habit.title, color=habit.color, status="due"
                )
            )

        due_count = len(entries)

        tasks = [
            CalendarTask(
                id=t.id,
                title=t.title,
                priority=t.priority,
                status=t.status.value if hasattr(t.status, "value") else str(t.status),
            )
            for t in due_tasks
        ]
        seen = {t.id for t in tasks}
        for t in done_tasks:
            if t.id in seen:
                continue
            tasks.append(
                CalendarTask(
                    id=t.id,
                    title=t.title,
                    priority=t.priority,
                    status=t.status.value if hasattr(t.status, "value") else str(t.status),
                    completed_here=True,
                )
            )

        focus_minutes = sum(f.duration_min for f in focus)

        return CalendarDay(
            date=day,
            in_month=in_month,
            is_today=day == today,
            is_future=is_future,
            habits=entries,
            tasks=tasks,
            habits_done=done,
            habits_due=due_count,
            tasks_due=len(due_tasks),
            tasks_completed=len(done_tasks),
            mood=getattr(journal, "mood", None),
            energy=getattr(journal, "energy", None),
            sleep_hours=getattr(journal, "sleep_hours", None),
            has_journal=journal is not None,
            focus_minutes=focus_minutes,
            focus_sessions=len(focus),
            intensity=(done / due_count) if due_count else 0.0,
        )

    @staticmethod
    def _scheduled_on(habit: Habit, day: date) -> bool:
        """Only for schedules that name a specific day.

        WEEKLY/MONTHLY habits commit to a count per period, not a date, so they
        are intentionally excluded rather than guessed onto a square.
        """
        if habit.frequency == Frequency.DAILY:
            return True
        if habit.frequency == Frequency.CUSTOM:
            return day.weekday() in set(habit.custom_days or [])
        return False
