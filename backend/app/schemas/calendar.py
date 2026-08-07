"""Calendar DTOs."""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel

from app.domain.enums import Priority

# `date: date` self-shadows under deferred annotations — alias the type first.
# Same trap that silently broke HabitLogCreate.date.
_Date = date


class CalendarHabit(BaseModel):
    id: str
    title: str
    color: Optional[str] = None
    #: "completed" | "partial" | "skipped" when logged; "due" when it was
    #: scheduled for that day but never logged.
    status: str


class CalendarTask(BaseModel):
    id: str
    title: str
    priority: Priority
    status: str
    #: True when the task was *finished* on this day rather than due on it.
    completed_here: bool = False


class CalendarDay(BaseModel):
    date: _Date
    in_month: bool
    is_today: bool
    is_future: bool

    habits: list[CalendarHabit] = []
    tasks: list[CalendarTask] = []

    habits_done: int = 0
    habits_due: int = 0
    tasks_due: int = 0
    tasks_completed: int = 0

    mood: Optional[float] = None
    energy: Optional[float] = None
    sleep_hours: Optional[float] = None
    has_journal: bool = False

    focus_minutes: int = 0
    focus_sessions: int = 0

    #: 0..1 completion for the day's habits — drives the cell's density dot.
    intensity: float = 0.0


class CalendarMonth(BaseModel):
    year: int
    month: int
    label: str
    #: Always whole weeks (Mon-first), so the grid is a clean 7xN.
    days: list[CalendarDay]

    total_habits_done: int = 0
    total_tasks_completed: int = 0
    total_focus_minutes: int = 0
    journal_days: int = 0
    perfect_days: int = 0
