"""Domain enumerations shared across models, schemas, and services.

All are ``str`` enums so they serialize cleanly to JSON and store as readable
text in SQLite.
"""
from __future__ import annotations

from enum import Enum


class Frequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"  # specific weekdays, see Habit.custom_days


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TimeOfDay(str, Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"
    ANY = "any"


class Difficulty(str, Enum):
    TRIVIAL = "trivial"
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class HabitLogStatus(str, Enum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    SKIPPED = "skipped"


class TaskStatus(str, Enum):
    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


# Statuses that count as "the habit happened" for streaks/consistency.
SUCCESS_STATUSES = frozenset({HabitLogStatus.COMPLETED, HabitLogStatus.PARTIAL})

# Task statuses considered still open / actionable.
OPEN_TASK_STATUSES = frozenset(
    {TaskStatus.BACKLOG, TaskStatus.TODO, TaskStatus.IN_PROGRESS}
)

WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
