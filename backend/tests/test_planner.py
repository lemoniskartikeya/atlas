"""API tests for the smart scheduler (Today's Plan).

These exercise the heuristic path: the test data dir has no trained model, so
``model_backed`` is False and ordering falls back to streak/time-of-day rules.
Every item must still honour the reason+confidence contract.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.planner_service import PlannerService

BASE = "/api/v1"


@pytest.fixture(autouse=True)
def _force_heuristic(monkeypatch):
    """Pin these tests to the model-free path.

    A trained model persisted by other tests into the shared data dir would
    otherwise leak in and change the ordering/reasons non-deterministically.
    The model-backed path is verified live, end-to-end.
    """
    monkeypatch.setattr(PlannerService, "_ml_predictions", lambda self, today: (None, None))


def _new_habit(client, **body):
    body.setdefault("title", "Habit")
    return client.post(f"{BASE}/habits", json=body).json()["id"]


def _all_items(plan):
    return [item for block in plan["blocks"] for item in block["items"]]


def test_plan_shape_and_time_of_day_buckets(client):
    morning = _new_habit(client, title="Morning pages", time_preference="morning")
    evening = _new_habit(client, title="Evening wind-down", time_preference="evening")

    plan = client.get(f"{BASE}/planner/today").json()

    for key in ("date", "generated_at", "now_block", "model_backed", "summary", "blocks", "open_count"):
        assert key in plan, f"missing plan key: {key}"

    # No model artifact in the test data dir -> heuristic ordering.
    assert plan["model_backed"] is False

    placement = {item["id"]: block["key"] for block in plan["blocks"] for item in block["items"]}
    assert placement[morning] == "morning"
    assert placement[evening] == "evening"

    # Blocks are emitted in chronological order.
    order = [b["key"] for b in plan["blocks"]]
    assert order == sorted(order, key=["morning", "afternoon", "evening"].index)


def test_reason_and_confidence_contract(client):
    _new_habit(client, title="Meditate", time_preference="morning")
    _new_habit(client, title="Read", time_preference="evening")

    plan = client.get(f"{BASE}/planner/today").json()
    items = _all_items(plan)
    assert items, "expected at least one planned item"
    for item in items:
        assert item["reason"], "every item needs a human-readable reason"
        assert 0.0 <= item["confidence"] <= 1.0


def test_done_habit_sinks_and_open_count(client):
    habit_id = _new_habit(client, title="Drink water", time_preference="morning")
    client.post(f"{BASE}/habits/{habit_id}/logs", json={})  # complete today

    plan = client.get(f"{BASE}/planner/today").json()
    items = _all_items(plan)
    done = next(i for i in items if i["id"] == habit_id)
    assert done["done"] is True
    assert plan["open_count"] == 0
    assert "clear" in plan["summary"].lower()


def test_streak_reason_is_explainable(client):
    habit_id = _new_habit(client, title="Journal", time_preference="evening")
    today = date.today()
    # Three consecutive prior days done; today left pending (grace keeps the streak).
    for offset in (3, 2, 1):
        d = (today - timedelta(days=offset)).isoformat()
        client.post(f"{BASE}/habits/{habit_id}/logs", json={"date": d})

    plan = client.get(f"{BASE}/planner/today").json()
    item = next(i for i in _all_items(plan) if i["id"] == habit_id)
    assert item["done"] is False
    assert "streak" in item["reason"].lower()
    assert item["confidence"] > 0.55  # streak protection is a stronger signal
