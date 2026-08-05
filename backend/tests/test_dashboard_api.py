"""API tests for the dashboard aggregate and journal upsert."""
from __future__ import annotations

from datetime import date

BASE = "/api/v1"


def test_dashboard_shape_and_streak(client):
    habit_id = client.post(
        f"{BASE}/habits", json={"title": "Morning pages", "time_preference": "morning"}
    ).json()["id"]
    client.post(f"{BASE}/habits/{habit_id}/logs", json={})

    body = client.get(f"{BASE}/dashboard").json()
    for key in (
        "greeting", "habits_today", "habits_completed", "habits_total",
        "weekly_consistency", "life_score", "life_score_trend", "focus_score",
        "top_streaks", "recommendations", "tasks_today",
    ):
        assert key in body, f"missing dashboard key: {key}"

    assert body["habits_total"] == 1
    assert body["habits_completed"] == 1
    assert isinstance(body["recommendations"], list)
    assert isinstance(body["life_score_trend"], list)


def test_journal_upsert_merges_fields(client):
    d = date.today().isoformat()

    first = client.put(f"{BASE}/journal/{d}", json={"mood": 4, "energy": 3, "sleep_hours": 6.0})
    assert first.status_code == 200
    assert first.json()["mood"] == 4

    merged = client.put(f"{BASE}/journal/{d}", json={"mood": 5}).json()
    assert merged["mood"] == 5
    assert merged["energy"] == 3  # untouched field preserved


def test_task_lifecycle(client):
    task_id = client.post(
        f"{BASE}/tasks", json={"title": "Do the thing", "priority": "high", "due_date": date.today().isoformat()}
    ).json()["id"]

    today_tasks = client.get(f"{BASE}/tasks", params={"scope": "today"}).json()
    assert any(t["id"] == task_id for t in today_tasks)

    completed = client.post(f"{BASE}/tasks/{task_id}/complete").json()
    assert completed["status"] == "done"
    assert completed["completed_at"] is not None
