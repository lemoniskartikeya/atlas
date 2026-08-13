"""Task rules that other layers agree on.

`on_time_outcome` is here rather than in the ML feature builder because it is
not an ML detail — it is the definition of whether a task was done in time, and
the prediction service needs the same answer to reason about deadlines without
scikit-learn installed. One definition, so a model and the fallback that
replaces it can never disagree about what counts as a miss.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from app.core.timeutil import local_day
from app.domain.enums import TaskStatus
from app.models.task import Task


def on_time_outcome(task: Task, today: date) -> Optional[int]:
    """1 done in time, 0 late or missed, None if this task settles nothing yet.

    Undated tasks are None: there is no "on time" without a time. Cancelled
    tasks are None too — deciding not to do something is a decision, and
    counting it as a failure would treat pruning your list the same as letting
    it rot.

    A task still open is only judged once its date has actually passed; before
    that it is simply unfinished, which is the normal state of a task.
    """
    if task.due_date is None or task.status == TaskStatus.CANCELLED:
        return None
    if task.status == TaskStatus.DONE:
        # local_day, not .date(): finishing at 23:30 is on time where the user
        # lives, even when that is already tomorrow in UTC.
        finished = local_day(task.completed_at)
        if finished is None:
            return None  # done, but we don't know when — unusable either way
        return 1 if finished <= task.due_date else 0
    return 0 if task.due_date < today else None
