"""ML service: orchestrates training, status, and today's explainable predictions.

Heavy imports (numpy/sklearn/joblib via app.learning.*) live here, so this module is
only imported when the optional ML router loads.
"""
from __future__ import annotations

from datetime import date
from math import isnan
from typing import Optional

from sqlalchemy.orm import Session

from app.learning import features, registry
from app.learning.model import train_model

MIN_SAMPLES = 40


def _clause(feature: str, v: float) -> Optional[str]:
    if v is None or (isinstance(v, float) and isnan(v)):
        return None
    if feature == "rate_7":
        return f"recent 7-day rate {v * 100:.0f}%"
    if feature == "rate_30":
        return f"30-day rate {v * 100:.0f}%"
    if feature == "streak_in":
        return f"a {int(v)}-day streak" if v > 0 else "no active streak"
    if feature == "done_prev":
        return "you did it last time" if v >= 0.5 else "you missed it last time"
    if feature == "is_weekend":
        return "it's the weekend" if v >= 0.5 else "it's a weekday"
    if feature == "days_since_last":
        return f"{int(v)}d since last done"
    if feature == "sleep_prev":
        return f"prior sleep {v:.1f}h"
    if feature == "mood_prev":
        return f"prior mood {v:.0f}/5"
    if feature == "energy_prev":
        return f"prior energy {v:.0f}/5"
    return None


def _explain(vec, top_features: list[str]) -> str:
    idx = {name: i for i, name in enumerate(features.FEATURE_NAMES)}
    clauses: list[str] = []
    for f in top_features:
        if f in idx:
            c = _clause(f, float(vec[idx[f]]))
            if c:
                clauses.append(c)
        if len(clauses) >= 3:
            break
    if not clauses:
        return "Based on your overall pattern."
    return "Weighed most by " + ", ".join(clauses) + "."


class MLService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def status(self) -> dict:
        meta = registry.latest_meta()
        if not meta:
            return {"trained": False}
        return {
            "trained": True,
            "version": meta["version"],
            "trained_at": meta["trained_at"],
            "model_type": meta.get("model_type"),
            "metrics": meta.get("metrics", {}),
        }

    def train(self) -> dict:
        X, y, dates = features.build_training(self.session)
        n = int(len(y))
        if n < MIN_SAMPLES or len(set(y.tolist())) < 2:
            return {
                "trained": False,
                "n_samples": n,
                "reason": (
                    f"Need at least {MIN_SAMPLES} settled examples across both outcomes "
                    f"to train (have {n})."
                ),
            }
        result = train_model(X, y, features.FEATURE_NAMES, dates)
        meta = registry.save(
            result.model,
            result.feature_names,
            result.kept_indices,
            result.metrics,
            result.importances,
        )
        return {"trained": True, "version": meta["version"], "metrics": result.metrics, "n_samples": n}

    def predict_today(self, today: Optional[date] = None) -> dict:
        bundle = registry.latest_bundle()
        if not bundle:
            return {"trained": False, "predictions": []}
        model = bundle["model"]
        kept = bundle.get("kept_indices")
        top_features = [imp["feature"] for imp in bundle.get("importances", [])[:6]]

        predictions = []
        for habit, vec, done in features.build_inference(self.session, today):
            model_vec = vec[kept] if kept is not None else vec
            proba = float(model.predict_proba(model_vec.reshape(1, -1))[0, 1])
            predictions.append(
                {
                    "habit_id": habit.id,
                    "title": habit.title,
                    "color": habit.color,
                    "probability": round(proba, 3),
                    "done_today": done,
                    "explanation": _explain(vec, top_features),
                }
            )
        predictions.sort(key=lambda p: p["probability"])  # riskiest first

        metrics = bundle.get("metrics", {})
        reliability = metrics.get("roc_auc")
        if reliability is None:
            reliability = metrics.get("accuracy")
        return {
            "trained": True,
            "version": bundle["version"],
            "model_type": type(model).__name__,
            "reliability": reliability,
            "metrics": metrics,
            "predictions": predictions,
        }
