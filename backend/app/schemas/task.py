"""Task-related API DTOs."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import Priority, TaskStatus

_Date = date


class TaskBase(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: Optional[str] = None
    project_id: Optional[str] = None
    parent_id: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    priority: Priority = Priority.MEDIUM
    tags: Optional[list[str]] = None
    labels: Optional[list[str]] = None
    estimated_effort_min: Optional[int] = Field(default=None, ge=0)
    actual_effort_min: Optional[int] = Field(default=None, ge=0)
    due_date: Optional[date] = None
    deadline: Optional[datetime] = None
    scheduled_for: Optional[date] = None
    context: Optional[str] = None
    energy_required: int = Field(default=3, ge=1, le=5)
    focus_required: int = Field(default=3, ge=1, le=5)
    location: Optional[str] = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    description: Optional[str] = None
    project_id: Optional[str] = None
    parent_id: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[Priority] = None
    tags: Optional[list[str]] = None
    labels: Optional[list[str]] = None
    estimated_effort_min: Optional[int] = Field(default=None, ge=0)
    actual_effort_min: Optional[int] = Field(default=None, ge=0)
    due_date: Optional[date] = None
    deadline: Optional[datetime] = None
    scheduled_for: Optional[date] = None
    context: Optional[str] = None
    energy_required: Optional[int] = Field(default=None, ge=1, le=5)
    focus_required: Optional[int] = Field(default=None, ge=1, le=5)
    location: Optional[str] = None


class TaskRead(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class CompletionDay(BaseModel):
    # `date: date` self-shadows during deferred-annotation resolution — the same
    # trap that silently broke HabitLogCreate.date. Alias the type to dodge it.
    date: _Date
    count: int


class CompletionStats(BaseModel):
    today: int
    this_week: int
    window: int
    all_time: int
    window_days: int
    per_day: list[CompletionDay]


class CompletedTasks(BaseModel):
    """Completion history: what got finished, and how much."""

    stats: CompletionStats
    tasks: list[TaskRead]
