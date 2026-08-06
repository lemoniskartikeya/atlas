"""Habit-related API DTOs."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import Difficulty, Frequency, HabitLogStatus, Priority, TimeOfDay

# A field literally named ``date`` shadows the ``date`` type during pydantic's
# deferred-annotation resolution (``from __future__ import annotations`` + a
# ``= None`` default), collapsing the field to NoneType. Reference the type via
# this alias so a ``date`` field keeps its real type.
_Date = date


class HabitBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = None
    frequency: Frequency = Frequency.DAILY
    custom_days: Optional[list[int]] = Field(default=None, description="Weekdays 0=Mon..6=Sun")
    target_per_period: int = Field(default=1, ge=1)
    priority: Priority = Priority.MEDIUM
    estimated_duration_min: Optional[int] = Field(default=None, ge=0)
    difficulty: Difficulty = Difficulty.MEDIUM
    motivation_level: int = Field(default=3, ge=1, le=5)
    required_energy: int = Field(default=3, ge=1, le=5)
    location: Optional[str] = None
    time_preference: TimeOfDay = TimeOfDay.ANY
    color: Optional[str] = None


class HabitCreate(HabitBase):
    pass


class HabitUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = None
    frequency: Optional[Frequency] = None
    custom_days: Optional[list[int]] = None
    target_per_period: Optional[int] = Field(default=None, ge=1)
    priority: Optional[Priority] = None
    estimated_duration_min: Optional[int] = Field(default=None, ge=0)
    difficulty: Optional[Difficulty] = None
    motivation_level: Optional[int] = Field(default=None, ge=1, le=5)
    required_energy: Optional[int] = Field(default=None, ge=1, le=5)
    location: Optional[str] = None
    time_preference: Optional[TimeOfDay] = None
    color: Optional[str] = None
    archived: Optional[bool] = None


class HabitLogCreate(BaseModel):
    date: Optional[_Date] = None  # defaults to today server-side
    status: HabitLogStatus = HabitLogStatus.COMPLETED
    partial_amount: Optional[float] = None
    reason: Optional[str] = None
    mood_after: Optional[int] = Field(default=None, ge=1, le=5)
    energy_before: Optional[int] = Field(default=None, ge=1, le=5)
    energy_after: Optional[int] = Field(default=None, ge=1, le=5)
    duration_min: Optional[int] = Field(default=None, ge=0)
    note: Optional[str] = None


class HabitLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    habit_id: str
    date: date
    status: HabitLogStatus
    partial_amount: Optional[float] = None
    reason: Optional[str] = None
    mood_after: Optional[int] = None
    energy_before: Optional[int] = None
    energy_after: Optional[int] = None
    duration_min: Optional[int] = None
    note: Optional[str] = None
    logged_at: datetime


class HabitStats(BaseModel):
    habit_id: str
    current_streak: int
    longest_streak: int
    total_completions: int
    success_rate: float  # 0..1 over all periods since first activity
    consistency_30d: float  # 0..1 over the last 30 days
    best_weekday: Optional[str] = None
    worst_weekday: Optional[str] = None
    most_productive_hour: Optional[int] = None
    average_duration_min: Optional[float] = None
    last_completed: Optional[date] = None


class HabitRead(HabitBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    archived: bool
    created_at: datetime
    updated_at: datetime


class HabitWithStats(HabitRead):
    stats: HabitStats
