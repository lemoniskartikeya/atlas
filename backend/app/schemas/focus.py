"""Focus-session DTOs."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class FocusSessionCreate(BaseModel):
    duration_min: int = Field(ge=1, le=600)
    distractions: int = Field(default=0, ge=0)
    note: Optional[str] = None
    task_id: Optional[str] = None
    started_at: Optional[datetime] = None  # defaults to now server-side


class FocusSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    started_at: datetime
    duration_min: int
    distractions: int
    note: Optional[str] = None
    task_id: Optional[str] = None
    created_at: datetime


class FocusStats(BaseModel):
    sessions_today: int
    minutes_today: int
    sessions_week: int
    minutes_week: int
    avg_distractions: Optional[float] = None  # over the last 7 days
    best_day_minutes: int  # best single day this week
