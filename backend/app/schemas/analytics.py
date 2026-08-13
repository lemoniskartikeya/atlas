"""Analytics API DTOs."""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel


class HeatmapCell(BaseModel):
    date: date
    count: int
    level: int  # 0..4 intensity bucket for rendering


class HeatmapResponse(BaseModel):
    start: date
    end: date
    total: int
    max_count: int
    cells: list[HeatmapCell]


class CategoryCount(BaseModel):
    category: str
    count: int


class TopHabit(BaseModel):
    id: str
    title: str
    current_streak: int
    longest_streak: int
    success_rate: float
    consistency_30d: float
    total_completions: int


class AnalyticsSummary(BaseModel):
    total_completions: int
    active_habits: int
    journal_entries: int
    tasks_completed: int
    tasks_open: int
    best_current_streak: int
    longest_streak_ever: int
    avg_mood: Optional[float] = None
    avg_energy: Optional[float] = None
    avg_sleep: Optional[float] = None
    deep_work_hours: float
    by_weekday: list[int]  # 7 ints, Mon..Sun
    by_category: list[CategoryCount]
    top_habits: list[TopHabit]


class WeeklyPoint(BaseModel):
    week_start: date
    label: str
    completions: int
    rate: float  # 0..1


class WeeklyResponse(BaseModel):
    weeks: list[WeeklyPoint]


class CorrelationPoint(BaseModel):
    date: date
    x: float
    y: float


class CorrelationPair(BaseModel):
    key: str
    x_label: str
    y_label: str
    coefficient: Optional[float] = None  # -1..1
    n: int
    interpretation: str
    points: list[CorrelationPoint]


class CorrelationsResponse(BaseModel):
    pairs: list[CorrelationPair]


class InsightOut(BaseModel):
    key: str
    text: str
    #: The arithmetic behind the sentence, shown alongside it. Always populated —
    #: a claim the user cannot check is not one this app makes.
    evidence: str
    tone: str  # "good" | "watch" | "neutral"


class InsightsResponse(BaseModel):
    generated_for: date
    days: int
    #: Empty whenever the data does not support a claim, which is the normal
    #: state of a new account. The page renders nothing rather than filler.
    insights: list[InsightOut]
