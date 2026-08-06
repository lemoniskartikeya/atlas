"""API tests for the prediction engine (expected completion, streak risk, burnout).

The heuristic path is pinned by default (a model persisted by other tests into
the shared data dir would otherwise leak in). The model-backed paths are made
deterministic by injecting fake gateway predictions.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

BASE = "/api/v1"


@pytest.fixture(autouse=True)
def _no_model(monkeypatch):
    """Default: force the model-free path across dashboard + prediction engine."""
    monkeypatch.setattr(
        "app.services.ml_gateway.habit_predictions", lambda session, today=None: (None, None)
    )


def _inject_predictions(monkeypatch, mapping: dict[str, float], reliability: float = 0.75):
    def _fake(session, today=None):
        preds = {
            hid: {"habit_id": hid, "probability": p, "done_today": False, "explanation": "test-why"}
            for hid, p in mapping.items()
        }
        return preds, reliability

    monkeypatch.setattr("app.services.ml_gateway.habit_predictions", _fake)


def _new_habit(client, **body):
    body.setdefault("title", "Habit")
    return client.post(f"{BASE}/habits", json=body).json()["id"]


# --------------------------------------------------------------- heuristic path

def test_prediction_report_shape(client):
    _new_habit(client, title="A")
    b = _new_habit(client, title="B")
    client.post(f"{BASE}/habits/{b}/logs", json={})  # one done today

    r = client.get(f"{BASE}/predictions").json()
    assert r["model_backed"] is False
    ec = r["expected_completion"]
    assert ec["due"] == 2 and ec["done"] == 1 and ec["remaining"] == 1
    assert 1.0 <= ec["expected_total"] <= 2.0
    assert 0.0 <= ec["expected_rate"] <= 1.0
    assert ec["reason"]
    assert r["burnout"]["level"] in {"low", "moderate", "elevated"}
    assert isinstance(r["streak_risks"], list)


def test_burnout_elevates_with_bad_signals(client):
    # Heavy load + poor wellbeing + zero completion -> drivers should fire.
    for i in range(5):
        _new_habit(client, title=f"H{i}")  # all due, none logged
    for i in range(6):
        client.post(f"{BASE}/tasks", json={"title": f"T{i}", "priority": "high"})
    today = date.today()
    for offset in (2, 1, 0):
        d = (today - timedelta(days=offset)).isoformat()
        client.put(f"{BASE}/journal/{d}", json={"sleep_hours": 5.0, "energy": 2})

    burnout = client.get(f"{BASE}/predictions").json()["burnout"]
    assert burnout["level"] in {"moderate", "elevated"}
    assert burnout["score"] >= 0.33
    assert burnout["drivers"], "expected named drivers"
    joined = " ".join(burnout["drivers"]).lower()
    assert "sleep" in joined and "completion" in joined


# ------------------------------------------------------------- model-backed path

def test_expected_completion_uses_model_probabilities(client, monkeypatch):
    h1 = _new_habit(client, title="Done one")
    h2 = _new_habit(client, title="Likely")
    h3 = _new_habit(client, title="Unlikely")
    client.post(f"{BASE}/habits/{h1}/logs", json={})  # done today

    _inject_predictions(monkeypatch, {h1: 0.9, h2: 0.8, h3: 0.2}, reliability=0.75)

    ec = client.get(f"{BASE}/predictions").json()["expected_completion"]
    assert ec["model_backed"] is True
    assert ec["confidence"] == 0.75
    # done(1) + 0.8 + 0.2 = 2.0 of 3
    assert ec["expected_total"] == pytest.approx(2.0, abs=1e-6)
    assert ec["due"] == 3 and ec["done"] == 1


def test_streak_break_risk_from_model(client, monkeypatch):
    h = _new_habit(client, title="Journal")
    today = date.today()
    for offset in (2, 1):  # 2-day streak, today pending
        client.post(f"{BASE}/habits/{h}/logs", json={"date": (today - timedelta(days=offset)).isoformat()})

    _inject_predictions(monkeypatch, {h: 0.3})  # 30% likely -> 70% break risk

    risks = client.get(f"{BASE}/predictions").json()["streak_risks"]
    assert len(risks) == 1
    risk = risks[0]
    assert risk["habit_id"] == h
    assert risk["level"] == "high"
    assert risk["risk"] == pytest.approx(0.7, abs=1e-6)
    assert risk["current_streak"] == 2
    assert "streak" in risk["reason"].lower()
