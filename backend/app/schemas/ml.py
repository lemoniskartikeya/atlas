"""ML API DTOs."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class MLMetrics(BaseModel):
    accuracy: Optional[float] = None
    roc_auc: Optional[float] = None
    brier: Optional[float] = None
    n_train: Optional[int] = None
    n_test: Optional[int] = None
    positive_rate: Optional[float] = None


class MLStatus(BaseModel):
    trained: bool
    version: Optional[str] = None
    trained_at: Optional[str] = None
    model_type: Optional[str] = None
    metrics: Optional[MLMetrics] = None


class TrainOutcome(BaseModel):
    trained: bool
    version: Optional[str] = None
    metrics: Optional[MLMetrics] = None
    n_samples: Optional[int] = None
    reason: Optional[str] = None


class HabitPrediction(BaseModel):
    habit_id: str
    title: str
    color: Optional[str] = None
    probability: float  # 0..1
    done_today: bool
    explanation: str


class PredictionsResponse(BaseModel):
    trained: bool
    version: Optional[str] = None
    model_type: Optional[str] = None
    reliability: Optional[float] = None
    metrics: Optional[MLMetrics] = None
    predictions: list[HabitPrediction] = []
