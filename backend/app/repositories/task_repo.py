"""Task repository."""
from __future__ import annotations

from datetime import date
from typing import Sequence

from sqlalchemy import select

from app.domain.enums import OPEN_TASK_STATUSES
from app.models.task import Task
from app.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    model = Task

    def list_all(self) -> Sequence[Task]:
        return list(self.session.scalars(select(Task).order_by(Task.created_at.desc())))

    def open_tasks(self) -> Sequence[Task]:
        return list(
            self.session.scalars(
                select(Task).where(Task.status.in_(list(OPEN_TASK_STATUSES)))
            )
        )

    def due_on_or_before(self, d: date) -> Sequence[Task]:
        return list(
            self.session.scalars(
                select(Task).where(
                    Task.status.in_(list(OPEN_TASK_STATUSES)),
                    Task.due_date.is_not(None),
                    Task.due_date <= d,
                )
            )
        )
