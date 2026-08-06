"""Prediction-engine DTOs.

Forward-looking, explainable signals derived from the completion model (when
trained) and transparent trend heuristics: how today is likely to end, which
streaks are at risk, and whether burnout signals are building. Every signal
carries a plain-English ``reason`` / ``drivers`` — no black boxes.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel


class ExpectedCompletion(BaseModel):
    due: int
    done: int
    remaining: int
    expected_total: float  # done + expected completions among what's left
    expected_rate: float  # expected_total / due, 0..1
    confidence: Optional[float] = None  # model reliability, when model-backed
    model_backed: bool
    reason: str


class StreakRisk(BaseModel):
    habit_id: str
    title: str
    current_streak: int
    probability: Optional[float] = None  # today's completion probability (model)
    risk: float  # 0..1 chance the streak breaks today
    level: str  # "high" | "medium"
    reason: str


class BurnoutSignal(BaseModel):
    score: float  # 0..1 composite
    level: str  # "low" | "moderate" | "elevated"
    drivers: list[str]  # the contributing factors, in plain language
    reason: str


class PredictionReport(BaseModel):
    date: date
    model_backed: bool
    reliability: Optional[float] = None
    expected_completion: ExpectedCompletion
    streak_risks: list[StreakRisk]
    burnout: BurnoutSignal
