"""Model-history DTOs."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ModelVersion(BaseModel):
    version: str
    trained_at: Optional[str] = None
    model_type: Optional[str] = None
    #: ROC-AUC, averaged over the rolling-origin folds. None for models trained
    #: on too little data to evaluate at all.
    roc_auc: Optional[float] = None
    #: Range across those folds. On a personal dataset this is wide, and it is
    #: the honest width of the estimate above — not a detail to hide.
    roc_auc_min: Optional[float] = None
    roc_auc_max: Optional[float] = None
    accuracy: Optional[float] = None
    #: Training examples used.
    n_samples: Optional[int] = None
    #: Total habit-log rows in the database at training time — the corpus the
    #: model was drawn from, so quality can be read against data volume.
    n_rows: Optional[int] = None
    n_test: Optional[int] = None
    #: Smallest minority-class count across folds. This, not the sample total,
    #: is what actually bounds how much the score can be trusted.
    n_test_neg_min: Optional[int] = None
    #: "rolling-origin" | "none". Absent on models trained before the
    #: evaluation was reworked — those carry a single-split score.
    eval: Optional[str] = None
    #: Why a model has no score, when it has none.
    eval_note: Optional[str] = None


class ModelHistory(BaseModel):
    versions: list[ModelVersion]
    total: int
    latest_roc_auc: Optional[float] = None
    best_roc_auc: Optional[float] = None
    #: Change in ROC-AUC from the previous scored version — did the last
    #: retrain actually help?
    delta_vs_previous: Optional[float] = None
    #: How much the score moves between folds of the *same* model. Any delta
    #: smaller than this is measurement noise, not a change in quality.
    noise_floor: Optional[float] = None
    #: True only when the delta is larger than that noise floor. None means
    #: "can't say" — nothing to compare, or the two versions were scored by
    #: different methods, which makes subtracting them meaningless.
    delta_is_meaningful: Optional[bool] = None
