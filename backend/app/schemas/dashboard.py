"""Dashboard aggregate DTOs."""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel

from app.domain.enums import HabitLogStatus, Priority, TimeOfDay
from app.schemas.journal import JournalRead
from app.schemas.task import TaskRead


class Recommendation(BaseModel):
    """An explainable suggestion.

    In Phase 1 these are transparent rule-based heuristics. Phase 4/5 replaces the
    generator with learned models — but the contract (a reason + a confidence on
    every recommendation) stays the same, by design.
    """

    id: str
    kind: str  # "habit" | "task" | "wellbeing" | "focus"
    title: str
    detail: str
    confidence: float  # 0..1
    reason: str  # human-readable "why this was suggested"


class HabitTodayItem(BaseModel):
    id: str
    title: str
    category: Optional[str] = None
    color: Optional[str] = None
    time_preference: TimeOfDay
    priority: Priority
    estimated_duration_min: Optional[int] = None
    current_streak: int
    status_today: Optional[HabitLogStatus] = None
    done_today: bool


class StreakItem(BaseModel):
    habit_id: str
    title: str
    current_streak: int
    longest_streak: int


class DashboardResponse(BaseModel):
    date: date
    greeting: str

    habits_today: list[HabitTodayItem]
    habits_completed: int
    habits_total: int

    tasks_today: list[TaskRead]
    tasks_open: int
    suggested_task: Optional[TaskRead] = None

    top_streaks: list[StreakItem]
    weekly_consistency: float  # 0..1 over the last 7 days
    life_score: float  # 0..100 composite
    life_score_trend: list[float]  # recent daily life-score proxy
    focus_score: Optional[float] = None  # 0..100

    mood: Optional[int] = None
    energy: Optional[int] = None
    sleep_hours: Optional[float] = None
    recent_journal: Optional[JournalRead] = None

    recommendations: list[Recommendation]
