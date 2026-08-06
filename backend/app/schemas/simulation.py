"""Habit-simulator DTOs (what-if scenarios over the completion model)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.domain.enums import TimeOfDay


class SimulationRequest(BaseModel):
    """A what-if scenario. Every field is optional — omitted means "unchanged"."""

    sleep_prev: Optional[float] = Field(default=None, ge=0, le=16)
    energy_prev: Optional[int] = Field(default=None, ge=1, le=5)
    mood_prev: Optional[int] = Field(default=None, ge=1, le=5)
    min_rate: Optional[float] = Field(default=None, ge=0, le=1)
    streak_in: Optional[int] = Field(default=None, ge=0, le=365)
    time_of_day: Optional[TimeOfDay] = None
    habit_id: Optional[str] = None  # scope wellbeing/ToD changes to one habit
    drop_habit_ids: list[str] = Field(default_factory=list)


class SimHabitRow(BaseModel):
    habit_id: str
    title: str
    color: Optional[str] = None
    done_today: bool
    baseline: float
    simulated: float
    delta: float


class SimulationResponse(BaseModel):
    available: bool
    reliability: Optional[float] = None
    due: int = 0
    baseline_expected: float = 0.0
    simulated_expected: float = 0.0
    delta_expected: float = 0.0
    levers: list[str] = Field(default_factory=list)
    summary: str = ""
    rows: list[SimHabitRow] = Field(default_factory=list)
