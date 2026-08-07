"""Task domain service."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.core.timeutil import local_day
from app.domain.enums import Priority, TaskStatus
from app.models.task import Task
from app.repositories.task_repo import TaskRepository
from app.schemas.task import TaskCreate, TaskUpdate

_PRIORITY_RANK = {
    Priority.CRITICAL: 0,
    Priority.HIGH: 1,
    Priority.MEDIUM: 2,
    Priority.LOW: 3,
}


class TaskService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.tasks = TaskRepository(session)

    def list_tasks(self, scope: str = "all", today: Optional[date] = None) -> Sequence[Task]:
        today = today or date.today()
        if scope == "today":
            items = [t for t in self.tasks.open_tasks() if self._is_today(t, today)]
        elif scope == "upcoming":
            items = [
                t
                for t in self.tasks.open_tasks()
                if (t.due_date and t.due_date > today)
                or (t.scheduled_for and t.scheduled_for > today)
            ]
        elif scope == "open":
            items = list(self.tasks.open_tasks())
        else:
            items = list(self.tasks.list_all())
        return self._sort(items, today)

    def get(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def create(self, data: TaskCreate) -> Task:
        task = Task(**data.model_dump())
        self.tasks.add(task)
        self.tasks.commit()
        return task

    def update(self, task: Task, data: TaskUpdate) -> Task:
        payload = data.model_dump(exclude_unset=True)
        new_status = payload.get("status")
        for key, value in payload.items():
            setattr(task, key, value)
        if new_status is not None:
            if new_status == TaskStatus.DONE and task.completed_at is None:
                task.completed_at = datetime.now(timezone.utc)
            elif new_status != TaskStatus.DONE:
                task.completed_at = None
        self.tasks.commit()
        return task

    def complete(self, task: Task) -> Task:
        task.status = TaskStatus.DONE
        task.completed_at = datetime.now(timezone.utc)
        self.tasks.commit()
        return task

    def delete(self, task: Task) -> None:
        self.tasks.delete(task)
        self.tasks.commit()

    # -------------------------------------------------------------- completions
    def completed_history(
        self, days: int = 30, limit: int = 200, today: Optional[date] = None
    ) -> tuple[list[Task], dict]:
        """Finished tasks plus a rollup of how much got done.

        Returns every completion inside the window (newest first) and counts for
        today / this week / the window / all time, with a per-day series so the
        UI can chart throughput.
        """
        today = today or date.today()
        rows = list(self.tasks.completed(limit=max(limit, 500)))

        def day_of(task: Task) -> date:
            return local_day(task.completed_at, today)

        window_start = today - timedelta(days=days - 1)
        week_start = today - timedelta(days=today.weekday())

        in_window = [t for t in rows if day_of(t) >= window_start]
        per_day = {window_start + timedelta(days=i): 0 for i in range(days)}
        for t in in_window:
            per_day[day_of(t)] = per_day.get(day_of(t), 0) + 1

        stats = {
            "today": sum(1 for t in rows if day_of(t) == today),
            "this_week": sum(1 for t in rows if day_of(t) >= week_start),
            "window": len(in_window),
            "all_time": len(rows),
            "window_days": days,
            "per_day": [
                {"date": d.isoformat(), "count": c} for d, c in sorted(per_day.items())
            ],
        }
        return in_window[:limit], stats

    def suggested_next(self, today: Optional[date] = None) -> Optional[Task]:
        today = today or date.today()
        candidates = list(self.tasks.open_tasks())
        if not candidates:
            return None

        def key(t: Task) -> tuple:
            overdue = 0 if (t.due_date and t.due_date <= today) else 1
            return (overdue, _PRIORITY_RANK.get(t.priority, 2), t.due_date or date.max)

        return sorted(candidates, key=key)[0]

    # ----------------------------------------------------------------- internals
    @staticmethod
    def _is_today(task: Task, today: date) -> bool:
        if task.scheduled_for == today:
            return True
        return bool(task.due_date and task.due_date <= today)

    @staticmethod
    def _sort(items: Sequence[Task], today: date) -> list[Task]:
        return sorted(
            items,
            key=lambda t: (_PRIORITY_RANK.get(t.priority, 2), t.due_date or date.max),
        )
