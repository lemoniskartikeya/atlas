"""Weekly-review DTOs.

The review is generated locally from the user's own data — no external service —
so it stays private and its every claim is traceable to a number.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel


class ReviewMetric(BaseModel):
    key: str
    label: str
    value: str
    delta: Optional[float] = None  # change vs. previous week (raw units)
    direction: Optional[str] = None  # "up" | "down" | "flat"
    hint: Optional[str] = None


class ReviewItem(BaseModel):
    title: str
    detail: str
    habit_id: Optional[str] = None


class WeeklyReview(BaseModel):
    start: date
    end: date
    label: str
    offset: int
    is_current: bool
    can_go_forward: bool

    completion_rate: float  # 0..1
    prev_completion_rate: Optional[float] = None
    completions: int
    due: int
    tasks_completed: int

    metrics: list[ReviewMetric]
    wins: list[ReviewItem]
    watchouts: list[ReviewItem]
    focus: list[str]
    narrative: str
