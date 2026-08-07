"""Model-history DTOs."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ModelVersion(BaseModel):
    version: str
    trained_at: Optional[str] = None
    model_type: Optional[str] = None
    #: Held-out ROC-AUC. None for models trained on too little data to evaluate.
    roc_auc: Optional[float] = None
    accuracy: Optional[float] = None
    #: Training examples used.
    n_samples: Optional[int] = None
    #: Total habit-log rows in the database at training time — the corpus the
    #: model was drawn from, so quality can be read against data volume.
    n_rows: Optional[int] = None
    n_test: Optional[int] = None


class ModelHistory(BaseModel):
    versions: list[ModelVersion]
    total: int
    latest_roc_auc: Optional[float] = None
    best_roc_auc: Optional[float] = None
    #: Change in ROC-AUC from the previous scored version — did the last
    #: retrain actually help?
    delta_vs_previous: Optional[float] = None
