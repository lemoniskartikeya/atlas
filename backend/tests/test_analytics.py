"""Tests for the analytics correlation math and endpoints."""
from __future__ import annotations

from app.services.analytics_service import interpret, pearson

BASE = "/api/v1"


def test_pearson_perfect_positive():
    assert round(pearson([1, 2, 3, 4], [2, 4, 6, 8]) or 0, 5) == 1.0


def test_pearson_perfect_negative():
    assert round(pearson([1, 2, 3, 4], [4, 3, 2, 1]) or 0, 5) == -1.0


def test_pearson_insufficient_or_constant():
    assert pearson([1, 2], [1, 2]) is None  # < 3 points
    assert pearson([1, 1, 1, 1], [1, 2, 3, 4]) is None  # zero variance in x


def test_interpret_low_sample():
    assert "Not enough" in interpret(0.9, 2, "Sleep", "completion rate")


def test_analytics_endpoints(client):
    habit_id = client.post(f"{BASE}/habits", json={"title": "A"}).json()["id"]
    client.post(f"{BASE}/habits/{habit_id}/logs", json={})
    client.put(f"{BASE}/journal/2026-08-01", json={"mood": 4, "energy": 3, "sleep_hours": 7})

    summary = client.get(f"{BASE}/analytics/summary")
    assert summary.status_code == 200
    body = summary.json()
    assert body["active_habits"] == 1
    assert body["total_completions"] == 1
    assert "top_habits" in body and len(body["by_weekday"]) == 7

    weekly = client.get(f"{BASE}/analytics/weekly", params={"weeks": 4})
    assert weekly.status_code == 200
    assert isinstance(weekly.json()["weeks"], list)

    corr = client.get(f"{BASE}/analytics/correlations", params={"days": 30})
    assert corr.status_code == 200
    keys = {p["key"] for p in corr.json()["pairs"]}
    assert keys == {"sleep", "mood", "energy"}
