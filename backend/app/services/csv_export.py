"""Your data, as spreadsheets.

Distinct from the JSON backup next door, which exists to be restored: this
exists to be opened. It is flat, readable, and slightly lossy on purpose —
nested structure becomes a joined string, because a spreadsheet has no idea
what to do with a list.

The most useful sheet is the one no table holds: `daily`, a row per day with
what was due, what got done, and how you slept — the shape you would have to
build by hand before you could chart anything.

Two details that look fussy and aren't:

* **The BOM.** Excel reads a UTF-8 file as the local codepage unless it starts
  with a byte-order mark, so without it every accented character in someone's
  notes arrives as mojibake.
* **Leading =, +, -, @.** A spreadsheet treats those as the start of a formula,
  which is how a habit named `=HYPERLINK(...)` becomes a live link in whoever
  you send the file to. Those cells get an apostrophe in front, which Excel and
  Sheets both strip on display. It is a visible change to the value, and the
  alternative is exporting something that executes.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable, Iterable, Optional

from sqlalchemy.orm import Session

from app.core.timeutil import local_day
from app.models.focus import FocusSession
from app.models.habit import Habit, HabitLog
from app.models.journal import JournalEntry
from app.models.note import Note
from app.models.task import Project, Task

#: Prefixed to any cell a spreadsheet would otherwise evaluate.
_FORMULA_STARTERS = ("=", "+", "-", "@", "\t", "\r")
#: Excel needs this to read the file as UTF-8.
BOM = "﻿"


@dataclass(frozen=True)
class Dataset:
    key: str
    label: str
    description: str
    headers: list[str]
    rows: Callable[[Session], Iterable[list]]


def _safe(value) -> str:
    """One cell, rendered as text a spreadsheet will treat as text."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, datetime):
        # Local, because every other date in the export is a local calendar day
        # and a column that silently mixes the two is worse than either.
        return value.astimezone().strftime("%Y-%m-%d %H:%M")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return ", ".join(_safe(v) for v in value)
    if hasattr(value, "value"):  # enum
        value = value.value

    text = str(value)
    if text.startswith(_FORMULA_STARTERS):
        return "'" + text
    return text


def render(dataset: Dataset, session: Session) -> str:
    """The whole sheet as one string, BOM included."""
    buffer = io.StringIO()
    # QUOTE_MINIMAL with the stdlib writer handles embedded commas, quotes and
    # newlines correctly; hand-rolled joining is where CSV exports go wrong.
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(dataset.headers)
    for row in dataset.rows(session):
        writer.writerow([_safe(cell) for cell in row])
    return BOM + buffer.getvalue()


# ------------------------------------------------------------------ datasets
def _habits(session: Session):
    from app.services.habit_service import HabitService

    service = HabitService(session)
    today = date.today()
    for habit in service.list_habits(include_archived=True):
        stats = service.compute_stats(habit, today)
        yield [
            habit.title,
            habit.category,
            habit.frequency,
            habit.priority,
            habit.difficulty,
            habit.time_preference,
            habit.estimated_duration_min,
            stats.current_streak,
            stats.longest_streak,
            round(stats.success_rate * 100, 1),
            round(stats.consistency_30d * 100, 1),
            stats.total_completions,
            habit.archived,
            habit.created_at,
        ]


def _habit_logs(session: Session):
    from app.repositories.habit_repo import HabitRepository

    for habit in HabitRepository(session).list_all(include_archived=True):
        for log in sorted(habit.logs, key=lambda l: l.date):
            yield [
                log.date,
                habit.title,
                habit.category,
                log.status,
                log.duration_min,
                log.mood_after,
                log.energy_before,
                log.energy_after,
                log.reason,
                log.note,
                log.logged_at,
            ]


def _tasks(session: Session):
    from app.repositories.task_repo import TaskRepository

    projects = {p.id: p.name for p in session.query(Project).all()}
    for task in TaskRepository(session).list_all():
        yield [
            task.title,
            task.status,
            task.priority,
            projects.get(task.project_id),
            task.due_date,
            task.scheduled_for,
            local_day(task.completed_at),
            task.estimated_effort_min,
            task.actual_effort_min,
            task.energy_required,
            task.focus_required,
            task.tags,
            task.created_at,
        ]


def _journal(session: Session):
    from app.repositories.journal_repo import JournalRepository

    for entry in sorted(JournalRepository(session).recent(5000), key=lambda j: j.date):
        yield [
            entry.date,
            entry.mood,
            entry.energy,
            entry.sleep_hours,
            entry.gratitude,
            entry.wins,
            entry.challenges,
            entry.lessons,
            entry.reflection,
        ]


def _focus(session: Session):
    tasks = {t.id: t.title for t in session.query(Task).all()}
    for s in session.query(FocusSession).order_by(FocusSession.started_at).all():
        yield [
            local_day(s.started_at),
            s.started_at,
            s.duration_min,
            s.distractions,
            tasks.get(s.task_id),
            s.note,
        ]


def _notes(session: Session):
    for n in session.query(Note).order_by(Note.updated_at.desc()).all():
        yield [n.title, n.date, n.is_daily, n.tags, len(n.content or ""), n.updated_at]


def _daily(session: Session):
    """A row per day: due, done, and how you felt. The sheet you'd build by hand."""
    from app.services.analytics_service import AnalyticsService

    for row in AnalyticsService(session).daily_frame(365, date.today()):
        yield [
            row["date"],
            row["due"],
            row["done"],
            round(row["rate"] * 100, 1) if row["rate"] is not None else None,
            row["mood"],
            row["energy"],
            row["sleep"],
        ]


DATASETS: list[Dataset] = [
    Dataset(
        "daily", "Daily summary",
        "One row per day for the last year: habits due and done, plus mood, energy and sleep.",
        ["date", "habits_due", "habits_done", "completion_pct", "mood", "energy", "sleep_hours"],
        _daily,
    ),
    Dataset(
        "habit_logs", "Habit log",
        "Every habit entry you've recorded, with how it felt at the time.",
        ["date", "habit", "category", "status", "duration_min", "mood_after",
         "energy_before", "energy_after", "skip_reason", "note", "logged_at"],
        _habit_logs,
    ),
    Dataset(
        "habits", "Habits",
        "One row per habit, with its streaks and success rates.",
        ["title", "category", "frequency", "priority", "difficulty", "time_preference",
         "estimated_duration_min", "current_streak", "longest_streak", "success_rate_pct",
         "consistency_30d_pct", "total_completions", "archived", "created_at"],
        _habits,
    ),
    Dataset(
        "tasks", "Tasks",
        "Every task, open and finished, with dates and effort.",
        ["title", "status", "priority", "project", "due_date", "scheduled_for",
         "completed_on", "estimated_effort_min", "actual_effort_min", "energy_required",
         "focus_required", "tags", "created_at"],
        _tasks,
    ),
    Dataset(
        "journal", "Journal",
        "Daily entries: mood, energy, sleep and what you wrote.",
        ["date", "mood", "energy", "sleep_hours", "gratitude", "wins", "challenges",
         "lessons", "reflection"],
        _journal,
    ),
    Dataset(
        "focus", "Focus sessions",
        "Every focus session: how long, how interrupted, and on what.",
        ["date", "started_at", "duration_min", "distractions", "task", "note"],
        _focus,
    ),
    Dataset(
        "notes", "Notes",
        "Note titles and sizes. The text itself stays in the app, where it's readable.",
        ["title", "date", "is_daily", "tags", "characters", "updated_at"],
        _notes,
    ),
]

_BY_KEY = {d.key: d for d in DATASETS}


def get(key: str) -> Optional[Dataset]:
    return _BY_KEY.get(key)


def filename(key: str, today: Optional[date] = None) -> str:
    return f"atlas-{key}-{(today or date.today()).isoformat()}.csv"
