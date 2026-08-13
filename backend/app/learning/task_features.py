"""Feature engineering for the task model.

The habit model answers "will you do this today?" for something that recurs.
Tasks don't recur — each one happens once — so the question is different:

    given everything known before its due date, was this task done on time?

That reframing is what makes tasks learnable at all. A habit carries its own
history; a task has none, so the behavioural signal has to come from the user's
record across *previous* tasks, and from the state of the backlog around it.

**What counts as settled.** A task with no due date is excluded outright: there
is nothing for it to be on time for. Cancelled tasks are excluded too —
abandoning something is a decision, not a failure to follow through, and
training on it would teach the model to treat deliberate pruning as slippage.
Everything else with a due date in the past is settled: done on or before the
date is a 1, done later or still open is a 0.

**Leakage.** Every example is scored *as of the end of its due date*, and every
feature is computable at that moment. Rolling features look only at tasks that
settled strictly earlier. The backlog count is the one that looks like it might
cheat and doesn't: knowing which tasks were still open on day D is something you
genuinely know on day D — it is the future of those tasks, not of this one, that
stays hidden.

Missing values stay NaN, as in the habit builder: HistGradientBoosting handles
them natively and journals are sparse.
"""
from __future__ import annotations

from datetime import date, timedelta
from math import cos, pi, sin
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session

from app.core.timeutil import local_day
from app.domain.enums import OPEN_TASK_STATUSES, Priority, TaskStatus
from app.domain.tasks import on_time_outcome
from app.models.task import Task
from app.repositories.journal_repo import JournalRepository
from app.repositories.task_repo import TaskRepository

FEATURE_NAMES = [
    "priority",
    "energy_required",
    "focus_required",
    "est_effort",
    "has_estimate",
    "has_description",
    "lead_time_days",
    "due_dow_sin",
    "due_dow_cos",
    "due_is_weekend",
    "n_subtasks",
    "is_subtask",
    "has_project",
    "n_tags",
    "was_scheduled",
    "recent_rate_7",
    "recent_rate_30",
    "on_time_streak",
    "open_backlog",
    "mood_prev",
    "energy_prev",
    "sleep_prev",
]

NAN = float("nan")
_PRIORITY = {Priority.LOW: 0, Priority.MEDIUM: 1, Priority.HIGH: 2, Priority.CRITICAL: 3}


def _created_day(task: Task) -> Optional[date]:
    return local_day(task.created_at)


def _done_day(task: Task) -> Optional[date]:
    return local_day(task.completed_at)


#: The label this model is fitted on. Re-exported rather than redefined: the
#: prediction service reasons about the same question without scikit-learn
#: installed, and two copies of this rule would eventually disagree.
outcome = on_time_outcome


def _static(task: Task) -> dict:
    created = _created_day(task)
    lead = (task.due_date - created).days if (created and task.due_date) else NAN
    return {
        "priority": float(_PRIORITY.get(task.priority, 1)),
        "energy_required": float(task.energy_required),
        "focus_required": float(task.focus_required),
        "est_effort": float(task.estimated_effort_min or 0),
        "has_estimate": 1.0 if task.estimated_effort_min else 0.0,
        "has_description": 1.0 if (task.description or "").strip() else 0.0,
        # Negative when a task was created after the date it was already due —
        # which happens, and is itself a signal about how it was planned.
        "lead_time_days": float(lead) if lead is not NAN else NAN,
        "n_subtasks": float(len(task.subtasks or [])),
        "is_subtask": 1.0 if task.parent_id else 0.0,
        "has_project": 1.0 if task.project_id else 0.0,
        "n_tags": float(len(task.tags or [])),
        "was_scheduled": 1.0 if task.scheduled_for else 0.0,
    }


def _calendar(d: date) -> dict:
    dow = d.weekday()
    return {
        "due_dow_sin": sin(2 * pi * dow / 7),
        "due_dow_cos": cos(2 * pi * dow / 7),
        "due_is_weekend": 1.0 if dow >= 5 else 0.0,
    }


def _behaviour(history: list[bool]) -> dict:
    """Your track record across earlier tasks, oldest→newest.

    Windowed by *task count* rather than by days: a week in which nothing was
    due says nothing about you, and a rate over an empty window is worse than
    no number at all.
    """
    if not history:
        return {
            "recent_rate_7": NAN,
            "recent_rate_30": NAN,
            "on_time_streak": 0.0,
        }
    last7 = history[-7:]
    last30 = history[-30:]
    streak = 0
    for v in reversed(history):
        if not v:
            break
        streak += 1
    return {
        "recent_rate_7": sum(last7) / len(last7),
        "recent_rate_30": sum(last30) / len(last30),
        "on_time_streak": float(streak),
    }


def _journal_prev(journals: dict, d: date) -> dict:
    j = journals.get(d - timedelta(days=1))
    return {
        "mood_prev": float(j.mood) if j and j.mood is not None else NAN,
        "energy_prev": float(j.energy) if j and j.energy is not None else NAN,
        "sleep_prev": float(j.sleep_hours) if j and j.sleep_hours is not None else NAN,
    }


def _open_on(tasks: list[Task], day: date) -> float:
    """How many tasks were sitting open on a given day.

    A crowded backlog is the most ordinary reason a task slips, and it is the
    only feature here that describes the surroundings rather than the task.

    Cancellation carries no timestamp of its own, so `updated_at` stands in for
    when it left the list — an approximation, and only for tasks the user threw
    away.
    """
    n = 0
    for t in tasks:
        created = _created_day(t)
        if created is None or created > day:
            continue
        if t.status == TaskStatus.DONE:
            finished = _done_day(t)
            if finished is not None and finished <= day:
                continue
        elif t.status == TaskStatus.CANCELLED:
            dropped = local_day(t.updated_at)
            if dropped is not None and dropped <= day:
                continue
        n += 1
    return float(n)


def _row(static: dict, cal: dict, beh: dict, jrn: dict, backlog: float) -> list[float]:
    merged = {**cal, **static, **beh, **jrn, "open_backlog": backlog}
    return [merged[name] for name in FEATURE_NAMES]


def build_training(session: Session, today: date | None = None):
    """Return (X, y, dates) over every settled, dated task."""
    today = today or date.today()
    tasks = list(TaskRepository(session).list_all())
    journals = {j.date: j for j in JournalRepository(session).recent(2000)}

    settled = [(t, outcome(t, today)) for t in tasks]
    settled = [(t, o) for t, o in settled if o is not None]
    # Due date is the moment the outcome is known, so it is also the order in
    # which the user lived through them — and what the rolling-origin
    # evaluation splits on.
    settled.sort(key=lambda pair: (pair[0].due_date, pair[0].id))

    rows: list[list[float]] = []
    labels: list[int] = []
    dates: list[date] = []
    history: list[bool] = []
    for task, label in settled:
        due = task.due_date
        rows.append(
            _row(
                _static(task),
                _calendar(due),
                _behaviour(history),
                _journal_prev(journals, due),
                _open_on(tasks, due),
            )
        )
        labels.append(label)
        dates.append(due)
        history.append(bool(label))

    X = np.array(rows, dtype=float) if rows else np.empty((0, len(FEATURE_NAMES)))
    y = np.array(labels, dtype=int)
    return X, y, dates


def build_inference(session: Session, today: date | None = None):
    """Return [(task, feature_vector)] for open tasks still in with a chance.

    Overdue tasks are left out on purpose: their outcome is already decided, and
    offering a probability for something that has already happened is not a
    prediction. The list is what the user can still act on today.
    """
    today = today or date.today()
    tasks = list(TaskRepository(session).list_all())
    journals = {j.date: j for j in JournalRepository(session).recent(2000)}

    history = [
        bool(o)
        for _t, o in sorted(
            (
                (t, outcome(t, today))
                for t in tasks
                if outcome(t, today) is not None and t.due_date < today
            ),
            key=lambda pair: (pair[0].due_date, pair[0].id),
        )
    ]
    backlog = _open_on(tasks, today)

    out = []
    for task in tasks:
        if task.status not in OPEN_TASK_STATUSES or task.due_date is None:
            continue
        if task.due_date < today:
            continue
        vec = _row(
            _static(task),
            _calendar(task.due_date),
            _behaviour(history),
            _journal_prev(journals, today),
            backlog,
        )
        out.append((task, np.array(vec, dtype=float)))
    return out
