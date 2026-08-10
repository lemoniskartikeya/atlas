"""Task repository."""
from __future__ import annotations

from datetime import date
from typing import Sequence

from sqlalchemy import select

from app.domain.enums import OPEN_TASK_STATUSES, TaskStatus
from app.models.task import Task
from app.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    model = Task

    def list_all(self) -> Sequence[Task]:
        return list(
            self.session.scalars(
                self.scoped(
                    select(Task).order_by(Task.created_at.desc(), Task.id.desc())
                )
            )
        )

    def open_tasks(self) -> Sequence[Task]:
        return list(
            self.session.scalars(
                self.scoped(select(Task).where(Task.status.in_(list(OPEN_TASK_STATUSES))))
            )
        )

    def completed(self, limit: int = 500) -> Sequence[Task]:
        """Completion history, most recently finished first.

        Date-range filtering is left to the caller: SQLite stores DateTime as a
        text column, so bounding the window in Python avoids depending on how a
        given driver renders timezone offsets into that string.
        """
        return list(
            self.session.scalars(
                self.scoped(
                    select(Task)
                    .where(Task.status == TaskStatus.DONE, Task.completed_at.is_not(None))
                    .order_by(Task.completed_at.desc(), Task.id.desc())
                    .limit(limit)
                )
            )
        )

    def due_on_or_before(self, d: date) -> Sequence[Task]:
        return list(
            self.session.scalars(
                self.scoped(
                    select(Task).where(
                        Task.status.in_(list(OPEN_TASK_STATUSES)),
                        Task.due_date.is_not(None),
                        Task.due_date <= d,
                    )
                )
            )
        )
