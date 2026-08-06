"""Single, guarded access point to the optional ML layer.

Every non-ML service that wants today's completion probabilities goes through
here, so the lazy import + "is a model even trained?" handling lives in one
place. Returns ``(None, None)`` whenever the ML stack is absent, a model hasn't
been trained yet, or inference fails — callers then fall back to heuristics.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session


def habit_predictions(
    session: Session, today: Optional[date] = None
) -> tuple[Optional[dict[str, dict]], Optional[float]]:
    """Return ``({habit_id: prediction_dict}, reliability)`` or ``(None, None)``.

    ``prediction_dict`` carries ``probability``, ``done_today`` and ``explanation``
    (see :meth:`MLService.predict_today`). ``reliability`` is the model's held-out
    ROC-AUC.

    Cheap gate first: ``registry.latest_meta()`` is a small JSON read that does
    *not* pull in scikit-learn. Only when a model actually exists do we import
    ``MLService`` (and thus numpy/scikit-learn). So callers like the dashboard
    stay lightweight until the day the user trains a model — keeping the ML stack
    genuinely optional, as promised.
    """
    try:
        from app.learning import registry
    except Exception:  # pragma: no cover - optional dependency missing
        return None, None
    if not registry.latest_meta():
        return None, None

    try:
        from app.services.ml_service import MLService
    except Exception:  # pragma: no cover - optional dependency missing
        return None, None
    try:
        result = MLService(session).predict_today(today)
    except Exception:  # pragma: no cover - defensive
        return None, None
    if not result.get("trained"):
        return None, None
    by_id = {p["habit_id"]: p for p in result.get("predictions", [])}
    return by_id, result.get("reliability")
