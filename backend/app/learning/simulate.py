"""Counterfactual perturbations for the habit simulator.

Pure, model-free helpers: take a habit's inference feature vector and apply a
user's "what-if" overrides (sleep, energy, mood, consistency, streak, time of
day), returning a new vector to re-score. Kept separate from the model so the
override maths is unit-testable without numpy models or a database.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from app.learning.features import FEATURE_NAMES

_IDX = {name: i for i, name in enumerate(FEATURE_NAMES)}
_TP_FEATURES = ("tp_morning", "tp_afternoon", "tp_evening", "tp_night", "tp_any")
_TP_BY_NAME = {
    "morning": "tp_morning",
    "afternoon": "tp_afternoon",
    "evening": "tp_evening",
    "night": "tp_night",
    "any": "tp_any",
}


def _is_nan(x: float) -> bool:
    return x != x


def apply_overrides(vec: np.ndarray, ov: dict) -> np.ndarray:
    """Return a copy of ``vec`` with the requested overrides applied.

    Every key is optional; ``None`` means "leave as-is". ``min_rate`` floors the
    rolling completion rates (treating NaN as "unknown", so it's raised to the
    floor). ``time_of_day`` rewrites the time-of-day one-hots.
    """
    v = vec.astype(float).copy()

    if ov.get("sleep_prev") is not None:
        v[_IDX["sleep_prev"]] = float(ov["sleep_prev"])
    if ov.get("energy_prev") is not None:
        v[_IDX["energy_prev"]] = float(ov["energy_prev"])
    if ov.get("mood_prev") is not None:
        v[_IDX["mood_prev"]] = float(ov["mood_prev"])

    if ov.get("min_rate") is not None:
        floor = float(ov["min_rate"])
        for name in ("rate_7", "rate_30"):
            cur = v[_IDX[name]]
            if _is_nan(cur) or cur < floor:
                v[_IDX[name]] = floor

    if ov.get("streak_in") is not None:
        v[_IDX["streak_in"]] = float(ov["streak_in"])

    tod = ov.get("time_of_day")
    if tod in _TP_BY_NAME:
        for name in _TP_FEATURES:
            v[_IDX[name]] = 0.0
        v[_IDX[_TP_BY_NAME[tod]]] = 1.0

    return v


def describe_levers(ov: dict, baseline: dict) -> list[str]:
    """Human-readable descriptions of the applied changes, for explainability."""
    levers: list[str] = []

    if ov.get("sleep_prev") is not None:
        was = baseline.get("sleep_prev")
        suffix = f" (recently ~{was:.1f}h)" if was is not None else ""
        levers.append(f"Sleep set to {float(ov['sleep_prev']):.1f}h{suffix}")
    if ov.get("energy_prev") is not None:
        levers.append(f"Energy set to {int(ov['energy_prev'])}/5")
    if ov.get("mood_prev") is not None:
        levers.append(f"Mood set to {int(ov['mood_prev'])}/5")
    if ov.get("min_rate") is not None:
        levers.append(f"Assume ≥{round(float(ov['min_rate']) * 100)}% recent consistency")
    if ov.get("streak_in") is not None:
        levers.append(f"Assume a {int(ov['streak_in'])}-day streak")
    if ov.get("time_of_day") in _TP_BY_NAME:
        levers.append(f"Move habits to the {ov['time_of_day']}")

    return levers


def baseline_wellbeing(vec: np.ndarray) -> dict[str, Optional[float]]:
    """Read yesterday's journal-derived values (shared across habits) for context."""
    out: dict[str, Optional[float]] = {}
    for name in ("sleep_prev", "energy_prev", "mood_prev"):
        x = float(vec[_IDX[name]])
        out[name] = None if _is_nan(x) else x
    return out
