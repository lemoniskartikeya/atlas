"""Tests for the habit simulator: pure overrides + no-model + model paths."""
from __future__ import annotations

import numpy as np
import pytest

from app.learning.features import FEATURE_NAMES
from app.learning.simulate import apply_overrides

BASE = "/api/v1"
_IDX = {n: i for i, n in enumerate(FEATURE_NAMES)}


# ------------------------------------------------------------- pure overrides

def test_apply_overrides_sets_features_and_time_of_day():
    vec = np.zeros(len(FEATURE_NAMES))
    vec[_IDX["rate_7"]] = np.nan
    vec[_IDX["rate_30"]] = 0.3
    vec[_IDX["tp_evening"]] = 1.0

    out = apply_overrides(
        vec,
        {
            "sleep_prev": 8.0,
            "energy_prev": 5,
            "mood_prev": 4,
            "min_rate": 0.9,
            "streak_in": 10,
            "time_of_day": "morning",
        },
    )

    assert out[_IDX["sleep_prev"]] == 8.0
    assert out[_IDX["energy_prev"]] == 5.0
    assert out[_IDX["mood_prev"]] == 4.0
    assert out[_IDX["streak_in"]] == 10.0
    # min_rate floors both, incl. the NaN one.
    assert out[_IDX["rate_7"]] == 0.9
    assert out[_IDX["rate_30"]] == 0.9
    # time-of-day one-hots rewritten.
    assert out[_IDX["tp_morning"]] == 1.0
    assert out[_IDX["tp_evening"]] == 0.0
    # original is untouched (copy semantics).
    assert vec[_IDX["tp_evening"]] == 1.0


def test_min_rate_does_not_lower_an_already_high_rate():
    vec = np.zeros(len(FEATURE_NAMES))
    vec[_IDX["rate_7"]] = 0.95
    out = apply_overrides(vec, {"min_rate": 0.5})
    assert out[_IDX["rate_7"]] == 0.95


# ------------------------------------------------------------- no-model path

def test_simulator_without_model_is_unavailable(client, monkeypatch):
    monkeypatch.setattr("app.learning.registry.latest_meta", lambda: None)
    r = client.post(f"{BASE}/simulator", json={"sleep_prev": 8.0}).json()
    assert r["available"] is False
    assert r["rows"] == []
    assert "train" in r["summary"].lower()


# ------------------------------------------------------------- model path

class _FakeModel:
    """Completion probability rises with prior sleep — deterministic for tests."""

    def predict_proba(self, X):
        vec = X[0]
        s = vec[_IDX["sleep_prev"]]
        p = 0.5 if s != s else max(0.01, min(0.99, 0.1 + 0.1 * float(s)))
        return np.array([[1 - p, p]])


def test_simulator_scores_counterfactual(client, monkeypatch):
    habit_id = client.post(f"{BASE}/habits", json={"title": "Deep work"}).json()["id"]

    bundle = {
        "model": _FakeModel(),
        "kept_indices": None,
        "feature_names": FEATURE_NAMES,
        "metrics": {"roc_auc": 0.7},
        "importances": [],
        "version": "test",
    }
    monkeypatch.setattr("app.learning.registry.latest_meta", lambda: {"version": "test"})
    monkeypatch.setattr("app.learning.registry.latest_bundle", lambda: bundle)

    r = client.post(f"{BASE}/simulator", json={"sleep_prev": 8.0}).json()

    assert r["available"] is True
    assert r["due"] == 1
    row = r["rows"][0]
    assert row["habit_id"] == habit_id
    # No journal -> baseline sleep is NaN -> 0.5; sleep=8 -> 0.9.
    assert row["baseline"] == pytest.approx(0.5, abs=1e-6)
    assert row["simulated"] == pytest.approx(0.9, abs=1e-6)
    assert row["delta"] == pytest.approx(0.4, abs=1e-6)
    assert r["delta_expected"] == pytest.approx(0.4, abs=1e-6)
    assert any("sleep" in lever.lower() for lever in r["levers"])
    assert r["summary"]


def test_time_of_day_lever_is_human_readable(client, monkeypatch):
    client.post(f"{BASE}/habits", json={"title": "Read"})
    bundle = {
        "model": _FakeModel(),
        "kept_indices": None,
        "feature_names": FEATURE_NAMES,
        "metrics": {"roc_auc": 0.7},
        "importances": [],
        "version": "test",
    }
    monkeypatch.setattr("app.learning.registry.latest_meta", lambda: {"version": "test"})
    monkeypatch.setattr("app.learning.registry.latest_bundle", lambda: bundle)

    r = client.post(f"{BASE}/simulator", json={"time_of_day": "evening"}).json()
    joined = " ".join(r["levers"])
    assert "evening" in joined
    assert "TimeOfDay" not in joined  # enum must render as its value
