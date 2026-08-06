"""Activity timeline: one reverse-chronological feed across the whole app.

Aggregates habit logs, computed streak milestones, task completions, journal
entries, and habit creations into a single stream. Pure local aggregation —
offset-paginated so it's robust to the many identical timestamps seed data can
carry.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from sqlalchemy import select

from app.domain.enums import SUCCESS_STATUSES, HabitLogStatus
from app.models.focus import FocusSession
from app.models.habit import Habit
from app.schemas.timeline import TimelineEvent, TimelineResponse
from app.services import streaks
from app.services.habit_service import HabitService
from app.services.journal_service import JournalService
from app.services.task_service import TaskService

# Streak lengths worth celebrating (avoids one event per day).
_STREAK_MILESTONES = {7, 14, 21, 30, 50, 75, 100, 150, 200, 300, 365, 500, 730}

_STATUS_VERB = {
    HabitLogStatus.COMPLETED: "Completed",
    HabitLogStatus.PARTIAL: "Partly did",
    HabitLogStatus.SKIPPED: "Skipped",
}

_ALL_KINDS = {"habit", "streak", "task", "journal", "habit_created", "focus"}


def _naive(dt: datetime) -> datetime:
    """Normalize to naive UTC so mixed tz-aware/naive timestamps sort together."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _ts_on(day: date, recorded: Optional[datetime]) -> datetime:
    """A sort/display timestamp anchored to the event's logical *day*.

    Habit logs default ``logged_at`` to insertion time, so seeded history would
    otherwise all clump at "now". Keep the day (``log.date``) and borrow only the
    recorded time-of-day, so events land on the right day of the timeline.
    """
    if recorded is not None:
        return datetime.combine(day, _naive(recorded).time())
    return datetime.combine(day, time(12))


class TimelineService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.habits = HabitService(session)
        self.tasks = TaskService(session)
        self.journals = JournalService(session)

    def build(
        self,
        limit: int = 50,
        offset: int = 0,
        kinds: Optional[Iterable[str]] = None,
        today: Optional[date] = None,
    ) -> TimelineResponse:
        today = today or date.today()
        wanted = {k for k in (kinds or _ALL_KINDS) if k in _ALL_KINDS} or _ALL_KINDS

        events = [e for e in self._all_events(today) if e.kind in wanted]
        events.sort(key=lambda e: e.timestamp, reverse=True)

        total = len(events)
        page = events[offset : offset + limit]
        return TimelineResponse(
            events=page,
            offset=offset,
            limit=limit,
            total=total,
            has_more=offset + limit < total,
        )

    # ------------------------------------------------------------- aggregation
    def _all_events(self, today: date) -> list[TimelineEvent]:
        events: list[TimelineEvent] = []
        habits = list(self.habits.list_habits(include_archived=True))

        for habit in habits:
            events.append(
                TimelineEvent(
                    id=f"created:{habit.id}",
                    kind="habit_created",
                    timestamp=_naive(habit.created_at),
                    date=habit.created_at.date() if habit.created_at else today,
                    title=f"Started tracking {habit.title}",
                    color=habit.color,
                    route="/habits",
                )
            )
            events.extend(self._habit_log_events(habit))
            events.extend(self._streak_events(habit, today))

        events.extend(self._task_events())
        events.extend(self._journal_events())
        events.extend(self._focus_events())
        return events

    def _habit_log_events(self, habit: Habit) -> list[TimelineEvent]:
        out: list[TimelineEvent] = []
        for log in habit.logs:
            ts = _ts_on(log.date, log.logged_at)
            verb = _STATUS_VERB.get(log.status, "Logged")
            detail = log.note or (log.reason if log.status == HabitLogStatus.SKIPPED else None)
            out.append(
                TimelineEvent(
                    id=f"log:{log.id}",
                    kind="habit",
                    timestamp=ts,
                    date=log.date,
                    title=f"{verb} {habit.title}",
                    detail=detail,
                    status=log.status.value,
                    color=habit.color,
                    route="/habits",
                )
            )
        return out

    def _streak_events(self, habit: Habit, today: date) -> list[TimelineEvent]:
        logs_by_date = {l.date: l for l in habit.logs}
        success = {d for d, l in logs_by_date.items() if l.status in SUCCESS_STATUSES}
        if not success:
            return []

        out: list[TimelineEvent] = []
        run = 0
        d = min(logs_by_date)
        while d <= today:
            if streaks.is_occurrence_day(habit.frequency, habit.custom_days, d):
                if d in success:
                    run += 1
                    if run in _STREAK_MILESTONES:
                        log = logs_by_date.get(d)
                        ts = _ts_on(d, log.logged_at if log else None)
                        out.append(
                            TimelineEvent(
                                id=f"streak:{habit.id}:{run}",
                                kind="streak",
                                timestamp=ts,
                                date=d,
                                title=f"{run}-day streak — {habit.title}",
                                detail="Milestone reached",
                                color=habit.color,
                                route="/habits",
                            )
                        )
                else:
                    run = 0
            d += timedelta(days=1)
        return out

    def _task_events(self) -> list[TimelineEvent]:
        out: list[TimelineEvent] = []
        for task in self.tasks.tasks.list_all():
            if not task.completed_at:
                continue
            ts = _naive(task.completed_at)
            out.append(
                TimelineEvent(
                    id=f"task:{task.id}",
                    kind="task",
                    timestamp=ts,
                    date=ts.date(),
                    title=f"Completed task — {task.title}",
                    route="/tasks",
                )
            )
        return out

    def _focus_events(self) -> list[TimelineEvent]:
        out: list[TimelineEvent] = []
        for fs in self.session.scalars(select(FocusSession)):
            ts = _naive(fs.started_at)
            detail = f"{fs.distractions} distraction{'s' if fs.distractions != 1 else ''}" if fs.distractions else None
            out.append(
                TimelineEvent(
                    id=f"focus:{fs.id}",
                    kind="focus",
                    timestamp=ts,
                    date=ts.date(),
                    title=f"Focused for {fs.duration_min} min",
                    detail=fs.note or detail,
                    route="/focus",
                )
            )
        return out

    def _journal_events(self) -> list[TimelineEvent]:
        out: list[TimelineEvent] = []
        for j in self.journals.recent(2000):
            bits = []
            if j.mood is not None:
                bits.append(f"mood {j.mood}/5")
            if j.energy is not None:
                bits.append(f"energy {j.energy}/5")
            if j.sleep_hours is not None:
                bits.append(f"{j.sleep_hours:g}h sleep")
            out.append(
                TimelineEvent(
                    id=f"journal:{j.date.isoformat()}",
                    kind="journal",
                    timestamp=datetime.combine(j.date, time(20)),
                    date=j.date,
                    title="Journaled",
                    detail=" · ".join(bits) if bits else None,
                    route="/journal",
                )
            )
        return out
