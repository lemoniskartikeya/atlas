"""Model-quality history.

Mounted unconditionally, unlike the rest of ``/ml``: the training history is
plain JSON on disk, so it stays readable in builds without the ML stack. Only
*training* needs scikit-learn.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.schemas.ml_history import ModelHistory, ModelVersion
from app.services import ml_gateway

router = APIRouter(prefix="/ml", tags=["ml"])


@router.get("/history", response_model=ModelHistory)
def history():
    versions: list[ModelVersion] = []
    for entry in ml_gateway.model_history():
        metrics = entry.get("metrics") or {}
        versions.append(
            ModelVersion(
                version=str(entry.get("version", "")),
                trained_at=entry.get("trained_at"),
                model_type=entry.get("model_type"),
                roc_auc=metrics.get("roc_auc"),
                accuracy=metrics.get("accuracy"),
                n_samples=metrics.get("n_samples"),
                n_rows=metrics.get("n_rows"),
                n_test=metrics.get("n_test"),
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

    return ModelHistory(
        versions=versions,
        total=len(versions),
        latest_roc_auc=latest,
        best_roc_auc=best,
        delta_vs_previous=delta,
    )
