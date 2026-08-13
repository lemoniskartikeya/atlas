"""ML API DTOs."""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel


class MLMetrics(BaseModel):
    accuracy: Optional[float] = None
    roc_auc: Optional[float] = None
    #: Range of ROC-AUC across the rolling-origin folds — the width of the
    #: estimate above, which on a personal dataset is substantial.
    roc_auc_min: Optional[float] = None
    roc_auc_max: Optional[float] = None
    brier: Optional[float] = None
    n_folds: Optional[int] = None
    #: Total examples the model was fitted on.
    n_examples: Optional[int] = None
    #: Kept for models trained before the rename; it always meant ``n_examples``.
    n_train: Optional[int] = None
    n_test: Optional[int] = None
    n_test_neg_min: Optional[int] = None
    positive_rate: Optional[float] = None
    eval: Optional[str] = None
    eval_note: Optional[str] = None


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


class TaskPrediction(BaseModel):
    task_id: str
    title: str
    due_date: date
    priority: str
    #: Probability the task lands on or before its due date.
    probability: float  # 0..1
    explanation: str


class TaskPredictionsResponse(BaseModel):
    trained: bool
    version: Optional[str] = None
    model_type: Optional[str] = None
    reliability: Optional[float] = None
    metrics: Optional[MLMetrics] = None
    #: Open, not-yet-overdue tasks only, riskiest first. Overdue tasks are
    #: already decided and are not predicted about.
    predictions: list[TaskPrediction] = []
