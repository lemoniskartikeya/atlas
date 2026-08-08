"""Model-quality history.

Mounted unconditionally, unlike the rest of ``/ml``: the training history is
plain JSON on disk, so it stays readable in builds without the ML stack. Only
*training* needs scikit-learn.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import current_user
from app.models.user import User
from app.schemas.ml_history import ModelHistory, ModelVersion
from app.services import ml_gateway

router = APIRouter(prefix="/ml", tags=["ml"])


@router.get("/history", response_model=ModelHistory)
def history(user: User = Depends(current_user)):
    versions: list[ModelVersion] = []
    for entry in ml_gateway.model_history(user.id):
        metrics = entry.get("metrics") or {}
        versions.append(
            ModelVersion(
                version=str(entry.get("version", "")),
                trained_at=entry.get("trained_at"),
                model_type=entry.get("model_type"),
                roc_auc=metrics.get("roc_auc"),
                roc_auc_min=metrics.get("roc_auc_min"),
                roc_auc_max=metrics.get("roc_auc_max"),
                accuracy=metrics.get("accuracy"),
                # ``n_train`` on models trained before the metric was renamed:
                # it always held the corpus size, never the train-split size.
                n_samples=metrics.get("n_samples") or metrics.get("n_examples")
                or metrics.get("n_train"),
                n_rows=metrics.get("n_rows"),
                n_test=metrics.get("n_test"),
                n_test_neg_min=metrics.get("n_test_neg_min"),
                eval=metrics.get("eval"),
                eval_note=metrics.get("eval_note"),
            )
        )

    scored = [v for v in versions if v.roc_auc is not None]
    best = max((v.roc_auc for v in scored), default=None)
    latest = scored[-1].roc_auc if scored else None
    # "Improving" compares the newest model against the one before it — the
    # question the user actually has is whether the last retrain helped.
    delta = (
        round(scored[-1].roc_auc - scored[-2].roc_auc, 4) if len(scored) >= 2 else None
    )

    # A single-split score on a personal dataset moves by more than most
    # retrains do, so a bare delta invites reading noise as a regression. Use
    # the newest model's own fold spread as the floor: if the same model varies
    # that much between folds, a smaller difference between models means
    # nothing.
    newest = scored[-1] if scored else None
    noise_floor = (
        round(newest.roc_auc_max - newest.roc_auc_min, 4)
        if newest and newest.roc_auc_max is not None and newest.roc_auc_min is not None
        else None
    )

    # Two scores are only comparable if they were measured the same way. A
    # rolling-origin mean and an old single-split score are different
    # quantities, and subtracting them produces a number that looks like a
    # verdict without being one. ``None`` means "can't say", not "no change".
    comparable = len(scored) >= 2 and scored[-1].eval == scored[-2].eval
    meaningful = (
        abs(delta) > noise_floor
        if comparable and delta is not None and noise_floor is not None
        else None
    )

    return ModelHistory(
        versions=versions,
        total=len(versions),
        latest_roc_auc=latest,
        best_roc_auc=best,
        delta_vs_previous=delta,
        noise_floor=noise_floor,
        delta_is_meaningful=meaningful,
    )
